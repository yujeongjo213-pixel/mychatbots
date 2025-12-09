import streamlit as st
from PIL import Image
from openai import OpenAI
import json
import os

# ---------------------------
# 1. 페이지 설정
# ---------------------------
st.set_page_config(
    page_title="여행 챗봇",
    page_icon="✈️",
    layout="wide"
)

# ---------------------------
# 2. API 및 데이터 로드
# ---------------------------
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except FileNotFoundError:
    st.error("비밀 키 파일(.streamlit/secrets.toml)을 찾을 수 없습니다.")
    st.stop()

client = OpenAI(api_key=api_key)

@st.cache_data
def load_data():
    try:
        with open('travel_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

travel_db = load_data()

# ---------------------------
# 3. 실험 조건 제어 (핵심 로직)
# ---------------------------
# URL 파라미터 읽기
query_params = st.query_params
group_id = query_params.get("group", "researcher")

# [기본값 설정]
use_ontology = True         # True: 여행 데이터 사용 / False: 일반 ChatGPT (Study 1 대조군)
data_filter = "All"         # All, High(Popularity), Low(Serendipity)
interaction = "Response"    # Response(수동), Clarifying(역질문)
hide_sidebar = False        # 참가자에게 사이드바 숨김 여부

# ---------------------------------------------------------
# [중요] 그룹별 조건 매핑 (선생님이 요청한 모든 조건)
# ---------------------------------------------------------

# --- Study 1: 매체 비교 (일반 LLM vs Ontology LLM) ---
if group_id == "S1_Basic":
    # 일반 ChatGPT (데이터 안 씀)
    use_ontology = False
    hide_sidebar = True

elif group_id == "S1_Ontology":
    # 여행 최적화 LLM (데이터 사용, 구조적 답변)
    use_ontology = True
    data_filter = "All" 
    interaction = "Response"
    hide_sidebar = True

# --- Study 2: 정보 속성 비교 (Popularity vs Serendipity) ---
elif group_id == "S2_Pop":
    use_ontology = True
    data_filter = "High" # Popularity
    interaction = "Response"
    hide_sidebar = True

elif group_id == "S2_Seren":
    use_ontology = True
    data_filter = "Low"  # Serendipity
    interaction = "Response"
    hide_sidebar = True

# --- Study 3: 2x2 상호작용 비교 (Pop/Seren x Resp/Clar) ---
elif group_id == "S3_Pop_Resp":
    use_ontology = True
    data_filter = "High"
    interaction = "Response"
    hide_sidebar = True

elif group_id == "S3_Pop_Clar":
    use_ontology = True
    data_filter = "High"
    interaction = "Clarifying"
    hide_sidebar = True

elif group_id == "S3_Seren_Resp":
    use_ontology = True
    data_filter = "Low"
    interaction = "Response"
    hide_sidebar = True

elif group_id == "S3_Seren_Clar":
    use_ontology = True
    data_filter = "Low"
    interaction = "Clarifying"
    hide_sidebar = True

# ---------------------------------------------------------

# [연구자용 수동 패널] (URL에 group 없으면 보임)
if not hide_sidebar:
    with st.sidebar:
        try:
            img = Image.open("Fitlab.png")
            st.image(img, caption="Fitlab", use_container_width=True)
        except:
            st.write("Fitlab")
        
        st.header("🔬 연구자용 설정")
        use_ontology = st.checkbox("온톨로지 데이터 사용", value=True)
        data_filter = st.radio("정보 속성", ["All", "High (Popularity)", "Low (Serendipity)"])
        interaction = st.radio("상호작용", ["Response (수동)", "Clarifying (역질문)"])
        
        if st.button("초기화"):
            st.session_state['messages'] = []
            st.rerun()

if hide_sidebar:
    st.markdown("""<style>[data-testid="stSidebar"] {display: none;}</style>""", unsafe_allow_html=True)


# ---------------------------
# 4. 프롬프트 엔지니어링
# ---------------------------
if "selected_city" not in st.session_state:
    st.session_state["selected_city"] = None

st.title("✈️ 여행 파트너 AI")

# [STEP 1] 도시 선택
if st.session_state["selected_city"] is None:
    st.subheader("여행지를 선택해주세요")
    cities = ["도쿄", "파리", "라스베거스", "로스앤젤레스", "시드니", "베이징", "뉴욕"]
    cols = st.columns(4)
    for i, city in enumerate(cities):
        if cols[i % 4].button(city, use_container_width=True):
            st.session_state["selected_city"] = city
            st.session_state["messages"] = []
            st.rerun()

# [STEP 2] 채팅 화면
else:
    # 상단 도시 표시
    c1, c2 = st.columns([8,2])
    c1.success(f"선택된 도시: **{st.session_state['selected_city']}**")
    if c2.button("도시 변경"):
        st.session_state["selected_city"] = None
        st.rerun()

    selected_city = st.session_state['selected_city']

    # --- 프롬프트 조립 시작 ---
    
    # 1. 일반 LLM 모드 (Study 1 대조군)
    if not use_ontology:
        system_prompt = f"""
        너는 '{selected_city}' 여행 가이드야. 
        일반적인 인터넷 정보(ChatGPT 지식)를 바탕으로 여행지를 추천해줘.
        친구처럼 편안하게 반말로 대답해줘.
        """
    
    # 2. 온톨로지 최적화 LLM 모드 (Study 1, 2, 3)
    else:
        # 데이터 필터링
        city_data = [d for d in travel_db if d['city'] == selected_city]
        
        if data_filter == "High (Popularity)" or data_filter == "High":
            final_data = [d for d in city_data if d['popularity'] == "High"]
        elif data_filter == "Low (Serendipity)" or data_filter == "Low":
            final_data = [d for d in city_data if d['popularity'] == "Low"]
        else:
            final_data = city_data # All

        # 프롬프트
        system_prompt = f"""
        너는 '{selected_city}' 여행 최적화 AI야.
        반드시 아래 [제공된 데이터]에 있는 장소만 우선적으로 추천해줘.
        외부 지식보다 이 데이터를 기반으로 답변해야 해.
        
        [제공된 데이터]
        {json.dumps(final_data, ensure_ascii=False)}
        """

        # 상호작용 조건 (Response vs Clarifying)
        if interaction == "Clarifying" or interaction == "Clarifying (역질문)":
            system_prompt += """
            [지침: 역질문 모드]
            1. 사용자의 첫 질문에 바로 장소를 나열하지 마.
            2. 반드시 "누구랑 가?", "어떤 분위기 좋아해?" 같은 **역질문(Clarifying Question)을 3개** 먼저 해.
            3. 사용자가 대답하면 "네 취향을 반영해서 우리가 함께 찾은 곳은..." 처럼 **공동 생산(Co-creation)** 느낌으로 추천해줘.
            """
        else:
            system_prompt += """
            [지침: 수동 응답 모드]
            1. 사용자가 물어보면 즉시 정보를 제공해.
            2. 되묻거나 대화를 길게 끌지 말고, 깔끔하게 정보만 전달해.
            """

    # --- 메시지 관리 ---
    if "messages" not in st.session_state or len(st.session_state["messages"]) == 0:
        st.session_state["messages"] = [{"role": "system", "content": system_prompt}]
    else:
        st.session_state["messages"][0] = {"role": "system", "content": system_prompt}

    # UI 출력
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("궁금한 점을 물어보세요!"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=st.session_state.messages
            )
            bot_reply = response.choices[0].message.content
            st.chat_message("assistant").markdown(bot_reply)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
        except Exception as e:
            st.error(f"Error: {e}")