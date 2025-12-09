import streamlit as st
from PIL import Image
from openai import OpenAI
import json
import os

# ---------------------------
# 1. 페이지 설정
# ---------------------------
st.set_page_config(
    page_title="여행 연구 챗봇",
    page_icon="✈️",  # 따옴표 오류 수정 완료
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
# 3. 실험 조건 제어 (URL 파라미터)
# ---------------------------
query_params = st.query_params
group_id = query_params.get("group", "researcher")

# [기본값 설정]
use_ontology = True         # True: 데이터 사용 / False: 일반 ChatGPT
data_filter = "All"         # All, High, Low
interaction = "Response"    # Response, Clarifying
hide_sidebar = False        # 참가자 모드 여부

# [그룹별 조건 매핑]
# Study 1: 매체 비교
if group_id == "S1_Basic":
    use_ontology = False
    hide_sidebar = True
elif group_id == "S1_Ontology":
    use_ontology = True
    data_filter = "All"
    interaction = "Response"
    hide_sidebar = True

# Study 2: 정보 속성 비교
elif group_id == "S2_Pop":
    use_ontology = True
    data_filter = "High"
    interaction = "Response"
    hide_sidebar = True
elif group_id == "S2_Seren":
    use_ontology = True
    data_filter = "Low"
    interaction = "Response"
    hide_sidebar = True

# Study 3: 상호작용 비교 (2x2)
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

# ---------------------------
# 4. 화면 구성 (로고 및 사이드바)
# ---------------------------

# [연구자 모드] 사이드바에 로고 및 패널 표시
if not hide_sidebar:
    with st.sidebar:
        try:
            img = Image.open("Fitlab.png")
            st.image(img, caption="Fitlab", use_container_width=True)
        except:
            st.warning("로고 파일(Fitlab.png) 없음")
        
        st.header("🔬 연구자용 설정")
        use_ontology = st.checkbox("온톨로지 데이터 사용", value=True)
        data_filter = st.radio("정보 속성", ["All", "High (Popularity)", "Low (Serendipity)"])
        interaction = st.radio("상호작용", ["Response (수동)", "Clarifying (역질문)"])
        
        if st.button("대화 초기화"):
            st.session_state['messages'] = []
            st.rerun()

# [참가자 모드] 사이드바 숨기고, 메인 화면 상단에 로고 표시
if hide_sidebar:
    # 사이드바 숨김 CSS
    st.markdown("""<style>[data-testid="stSidebar"] {display: none;}</style>""", unsafe_allow_html=True)
    
    # 메인 상단 로고 표시
    try:
        col1, col2 = st.columns([1, 9])
        with col1:
            img = Image.open("Fitlab.png")
            st.image(img, use_container_width=True)
    except:
        pass

# ---------------------------
# 5. 도시 선택 및 채팅 인터페이스
# ---------------------------
if "selected_city" not in st.session_state:
    st.session_state["selected_city"] = None

st.title("✈️ 나만의 여행 공동 생산자")

# [STEP 1] 도시 선택 화면
if st.session_state["selected_city"] is None:
    st.subheader("떠나고 싶은 여행지를 선택해주세요")
    # LA를 로스앤젤레스로 수정
    cities = ["도쿄", "파리", "라스베거스", "로스앤젤레스", "시드니", "베이징", "뉴욕"]
    cols = st.columns(4)
    for i, city in enumerate(cities):
        if cols[i % 4].button(city, use_container_width=True):
            st.session_state["selected_city"] = city
            st.session_state["messages"] = []
            st.rerun()

# [STEP 2] 채팅 화면
else:
    # 상단 도시 표시 및 변경 버튼
    c1, c2 = st.columns([8,2])
    c1.success(f"선택된 도시: **{st.session_state['selected_city']}**")
    if c2.button("도시 변경"):
        st.session_state["selected_city"] = None
        st.rerun()

    selected_city = st.session_state['selected_city']

    # --- 프롬프트 조립 (풍부한 설명 + 조건 반영) ---
    
    # 1. 일반 LLM (Study 1 대조군)
    if not use_ontology:
        system_prompt = f"""
        너는 '{selected_city}' 여행 가이드야. 
        일반적인 인터넷 정보(ChatGPT 지식)를 바탕으로 여행지를 추천해줘.
        친구처럼 편안하게 반말로 대답해줘.
        """
    
    # 2. 온톨로지 최적화 LLM (Study 1, 2, 3)
    else:
        # 데이터 필터링
        city_data = [d for d in travel_db if d['city'] == selected_city]
        
        if "High" in data_filter:
            final_data = [d for d in city_data if d['popularity'] == "High"]
        elif "Low" in data_filter:
            final_data = [d for d in city_data if d['popularity'] == "Low"]
        else:
            final_data = city_data # All

        # [수정됨] 풍부한 설명을 유도하는 프롬프트
        system_prompt = f"""
        너는 '{selected_city}' 여행 최적화 AI야.
        
        [핵심 지침]
        1. **장소 선정:** 반드시 아래 [제공된 데이터] 목록에 있는 장소들 중에서만 골라서 추천해.
        2. **설명 방식:** [제공된 데이터]의 정보를 뼈대로 하되, **네가 원래 알고 있는 지식(역사, 꿀팁, 맛집 등)을 살을 붙여서 아주 풍성하게** 설명해줘. 단답형 금지.
        3. 말투는 친구처럼 친근한 반말로 해줘.
        
        [제공된 데이터]
        {json.dumps(final_data, ensure_ascii=False)}
        """

        # 상호작용 조건 (Study 3)
        if interaction == "Clarifying" or interaction == "Clarifying (역질문)":
            system_prompt += """
            [대화 스타일: 역질문 모드]
            1. 사용자의 첫 질문에 바로 추천 리스트를 주지 마.
            2. 반드시 "누구랑 가?", "어떤 분위기 좋아해?" 같은 **역질문(Clarifying Question)을 2~3개** 먼저 던져서 구체적인 상황을 파악해.
            3. 사용자가 대답하면, "네 상황을 보니 여기가 딱이야!"라며 **공동 생산(Co-creation)**하는 느낌으로 추천해.
            """
        else:
            system_prompt += """
            [대화 스타일: 수동 응답 모드]
            1. 사용자가 물어보면 뜸 들이지 말고 즉시 추천 장소를 알려줘.
            2. 되묻거나(Questioning) 대화를 길게 끌지 말고, 요청한 정보를 시원시원하게 전달해.
            """

    # --- 메시지 관리 ---
    if "messages" not in st.session_state or len(st.session_state["messages"]) == 0:
        st.session_state["messages"] = [{"role": "system", "content": system_prompt}]
    else:
        # 조건 변경 시 프롬프트 갱신
        st.session_state["messages"][0] = {"role": "system", "content": system_prompt}

    # --- 채팅 UI 출력 ---
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # --- 사용자 입력 ---
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