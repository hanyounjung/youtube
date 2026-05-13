import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from collections import Counter
from konlpy.tag import Okt

st.set_page_config(page_title="유튜브 댓글 분석기", layout="wide")

st.title("📺 유튜브 댓글 분석 웹앱")
st.caption("유튜브 영상 링크를 입력하면 댓글을 수집하고 시간대별 추이, 좋아요 수, 자주 등장하는 단어를 분석합니다.")

API_KEY = st.secrets["AIzaSyCM44tv2aR1f7Ch0fANaQTTzY-WquSE5zY"]

okt = Okt()

def extract_video_id(url):
    patterns = [
        r"v=([^&]+)",
        r"youtu\.be/([^?&]+)",
        r"shorts/([^?&]+)",
        r"embed/([^?&]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_comments(video_id, max_pages=10):
    comments = []
    page_token = ""

    for _ in range(max_pages):
        url = "https://www.googleapis.com/youtube/v3/commentThreads"
        params = {
            "part": "snippet",
            "videoId": video_id,
            "key": API_KEY,
            "maxResults": 100,
            "order": "time",
            "pageToken": page_token,
            "textFormat": "plainText"
        }

        res = requests.get(url, params=params)
        data = res.json()

        if "error" in data:
            st.error(data["error"]["message"])
            break

        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "작성자": snippet.get("authorDisplayName"),
                "댓글": snippet.get("textDisplay"),
                "좋아요수": snippet.get("likeCount", 0),
                "작성시간": snippet.get("publishedAt")
            })

        page_token = data.get("nextPageToken", "")
        if not page_token:
            break

    return pd.DataFrame(comments)

def extract_keywords(texts):
    words = []
    stopwords = {
        "그리고", "하지만", "진짜", "너무", "정말", "영상", "댓글",
        "입니다", "합니다", "있다", "없다", "ㅋㅋ", "ㅎㅎ", "ㅠㅠ"
    }

    for text in texts:
        nouns = okt.nouns(str(text))
        words.extend([w for w in nouns if len(w) >= 2 and w not in stopwords])

    return Counter(words)

youtube_url = st.text_input("유튜브 영상 링크 입력")

max_pages = st.slider(
    "수집할 댓글 페이지 수",
    min_value=1,
    max_value=30,
    value=10,
    help="1페이지당 최대 100개 댓글을 수집합니다."
)

if st.button("댓글 분석 시작"):
    video_id = extract_video_id(youtube_url)

    if not video_id:
        st.warning("올바른 유튜브 영상 링크를 입력해주세요.")
        st.stop()

    with st.spinner("댓글을 수집하고 분석하는 중입니다..."):
        df = get_comments(video_id, max_pages=max_pages)

    if df.empty:
        st.warning("수집된 댓글이 없습니다. 댓글이 비활성화되었거나 API 제한이 있을 수 있습니다.")
        st.stop()

    df["작성시간"] = pd.to_datetime(df["작성시간"])
    df["날짜"] = df["작성시간"].dt.date
    df["시간대"] = df["작성시간"].dt.hour

    st.success(f"총 {len(df)}개의 댓글을 수집했습니다.")

    col1, col2, col3 = st.columns(3)
    col1.metric("총 댓글 수", len(df))
    col2.metric("평균 좋아요 수", round(df["좋아요수"].mean(), 2))
    col3.metric("최대 좋아요 수", int(df["좋아요수"].max()))

    st.subheader("📄 댓글 데이터")
    st.dataframe(df, use_container_width=True)

    st.subheader("🕒 날짜별 댓글 추이")
    daily = df.groupby("날짜").size().reset_index(name="댓글수")
    fig_daily = px.line(daily, x="날짜", y="댓글수", markers=True)
    st.plotly_chart(fig_daily, use_container_width=True)

    st.subheader("⏰ 시간대별 댓글 수")
    hourly = df.groupby("시간대").size().reset_index(name="댓글수")
    fig_hourly = px.bar(hourly, x="시간대", y="댓글수")
    st.plotly_chart(fig_hourly, use_container_width=True)

    st.subheader("👍 좋아요 수 상위 댓글")
    top_like = df.sort_values("좋아요수", ascending=False).head(10)
    st.dataframe(top_like[["작성자", "댓글", "좋아요수", "작성시간"]], use_container_width=True)

    st.subheader("☁️ 자주 등장하는 단어 워드클라우드")
    counter = extract_keywords(df["댓글"])

    if counter:
        wc = WordCloud(
            font_path="NanumGothic.ttf",
            width=1000,
            height=500,
            background_color="white"
        ).generate_from_frequencies(counter)

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)

        st.subheader("🔤 단어 빈도 TOP 20")
        word_df = pd.DataFrame(counter.most_common(20), columns=["단어", "빈도"])
        st.dataframe(word_df, use_container_width=True)

        fig_words = px.bar(word_df, x="단어", y="빈도")
        st.plotly_chart(fig_words, use_container_width=True)
    else:
        st.info("분석할 단어가 충분하지 않습니다.")

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 댓글 데이터 CSV 다운로드",
        data=csv,
        file_name="youtube_comments.csv",
        mime="text/csv"
    )
