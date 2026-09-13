"""Streamlit frontend for the URL Shortener.

Communicates with the FastAPI backend over HTTP only.
Never touches SQLite directly.
"""

import io

import qrcode
import requests
import streamlit as st

API_BASE = "http://localhost:8000"
SHORTEN_URL = f"{API_BASE}/api/shorten"
STATS_URL_TEMPLATE = API_BASE + "/api/stats/{short_code}"
REQUEST_TIMEOUT = 10

BACKEND_DOWN_MESSAGE = (
    "Cannot connect to the FastAPI backend. "
    "Please make sure it is running with "
    "`uvicorn backend.main:app --reload` on http://localhost:8000."
)


def _backend_detail(response: requests.Response, fallback: str) -> str:
    """Extract a user-friendly error message from a backend response."""
    try:
        data = response.json()
    except ValueError:
        return fallback
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list) and detail:
            # Pydantic validation errors come back as a list; summarize simply.
            return "Invalid request. Please check your input and try again."
    return fallback


def _make_qr_png(data: str) -> bytes:
    """Generate a PNG-encoded QR code for the given string."""
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _init_state() -> None:
    defaults = {
        "short_code": None,
        "short_url": None,
        "long_url": None,
        "qr_png": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _shorten_section() -> None:
    st.header("Shorten a URL")
    long_url_input = st.text_input(
        "Enter a long URL",
        placeholder="https://example.com/some/long/path",
        key="long_url_input",
    )

    if st.button("Shorten URL"):
        long_url = (long_url_input or "").strip()
        if not long_url:
            st.warning("Please enter a URL to shorten.")
        else:
            try:
                response = requests.post(
                    SHORTEN_URL, json={"long_url": long_url}, timeout=REQUEST_TIMEOUT
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                st.error(BACKEND_DOWN_MESSAGE)
            except requests.exceptions.RequestException:
                st.error("Could not reach the backend. Please try again later.")
            else:
                if response.status_code == 201:
                    try:
                        data = response.json()
                    except ValueError:
                        st.error("Received an unexpected response from the backend.")
                    else:
                        short_code = data.get("short_code") if isinstance(data, dict) else None
                        short_url = data.get("short_url") if isinstance(data, dict) else None
                        long_url_resp = data.get("long_url") if isinstance(data, dict) else None
                        if not short_code or not short_url or not long_url_resp:
                            st.error("Received an unexpected response from the backend.")
                        else:
                            st.session_state["short_code"] = short_code
                            st.session_state["short_url"] = short_url
                            st.session_state["long_url"] = long_url_resp
                            try:
                                st.session_state["qr_png"] = _make_qr_png(short_url)
                            except Exception:
                                st.session_state["qr_png"] = None
                                st.error("Short URL created, but the QR code could not be generated.")
                            else:
                                st.success("Short URL created!")
                elif response.status_code == 400:
                    st.error(_backend_detail(response, "That URL looks invalid. Please check it and try again."))
                elif response.status_code == 500:
                    st.error("The backend encountered an error. Please try again later.")
                else:
                    st.error(_backend_detail(response, "Something went wrong. Please try again later."))

    # Persisted result: stays visible across normal Streamlit reruns.
    if st.session_state.get("short_url"):
        st.subheader("Your short URL")
        st.write("Original URL:")
        st.write(st.session_state.get("long_url"))
        st.write("Short code:")
        st.code(st.session_state.get("short_code"))
        st.write("Short URL:")
        st.write(st.session_state.get("short_url"))
        st.link_button("Open short URL", st.session_state.get("short_url"))

        qr_png = st.session_state.get("qr_png")
        if qr_png:
            st.subheader("QR code")
            st.image(qr_png, caption="Scan to open the short URL")
            st.download_button(
                label="Download QR code (PNG)",
                data=qr_png,
                file_name=f"{st.session_state.get('short_code')}_qr.png",
                mime="image/png",
            )


def _analytics_section() -> None:
    st.header("View Analytics")
    code_input = st.text_input("Enter a short code", placeholder="e.g. Ab3xYz", key="stats_code_input")

    if st.button("View Analytics"):
        short_code = (code_input or "").strip()
        if not short_code:
            st.warning("Please enter a short code.")
        else:
            try:
                response = requests.get(
                    STATS_URL_TEMPLATE.format(short_code=short_code),
                    timeout=REQUEST_TIMEOUT,
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                st.error(BACKEND_DOWN_MESSAGE)
            except requests.exceptions.RequestException:
                st.error("Could not reach the backend. Please try again later.")
            else:
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError:
                        st.error("Received an unexpected response from the backend.")
                    else:
                        if not isinstance(data, dict):
                            st.error("Received an unexpected response from the backend.")
                        else:
                            try:
                                click_count = data.get("click_count", 0)
                                created_at = data.get("created_at", "—")
                                last_clicked_at = data.get("last_clicked_at") or "—"
                                original_url = data.get("long_url", "—")
                                clicks_by_day = data.get("clicks_by_day", [])
                            except AttributeError:
                                st.error("Received an unexpected response from the backend.")
                            else:
                                st.metric("Total Clicks", click_count)
                                st.write("Original URL:")
                                st.write(original_url)
                                st.write(f"Created At: {created_at}")
                                st.write(f"Last Clicked At: {last_clicked_at}")

                                if not clicks_by_day:
                                    st.info("No clicks yet. Visit the short URL, then check back here.")
                                else:
                                    try:
                                        # clicks_by_day: [{"date": "YYYY-MM-DD", "clicks": N}, ...]
                                        # Use only Streamlit's built-in chart (no pandas/plotly/matplotlib).
                                        chart_rows = [
                                            {"date": row.get("date"), "clicks": row.get("clicks")}
                                            for row in clicks_by_day
                                            if isinstance(row, dict)
                                            and row.get("date") is not None
                                            and row.get("clicks") is not None
                                        ]
                                        if not chart_rows:
                                            st.info("No clicks yet. Visit the short URL, then check back here.")
                                        else:
                                            st.bar_chart(chart_rows, x="date", y="clicks")
                                    except Exception:
                                        st.error("Click data could not be displayed as a chart.")
                elif response.status_code == 404:
                    st.error("Short code not found. Please check the code and try again.")
                elif response.status_code == 500:
                    st.error("The backend encountered an error. Please try again later.")
                else:
                    st.error(_backend_detail(response, "Something went wrong. Please try again later."))


def main() -> None:
    st.set_page_config(page_title="URL Shortener", layout="centered")
    st.title("URL Shortener")
    st.write(
        "Create short URLs from long links and view click analytics "
        "such as total clicks and clicks per day."
    )

    _init_state()
    _shorten_section()
    st.divider()
    _analytics_section()


if __name__ == "__main__":
    main()
