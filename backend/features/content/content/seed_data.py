"""콘텐츠 동 산업 풀 시드 데이터 (newspipeline 원본 이식).

mentors 마이그레이션이 이 파일을 import해서 4개 테이블을 채운다:
  content_industries              ← INDUSTRY_COMPANIES의 unique industry_ko
  content_industry_keywords       ← INDUSTRY_COMPANIES의 (industry, sub_keyword) 페어
  content_master_keywords         ← KEYWORD_SCHEDULE (priority/interval/slot)
  content_master_keyword_companies ← INDUSTRY_COMPANIES의 [(company, country)]

테이블 설명:

* ``INDUSTRY_COMPANIES`` — 각 (industry_ko, sub_keyword_ko) 페어가 어떤
  대표 기업을 검색해야 하는지. 회사는 여러 sub_keyword에 등장 가능 (N:M).

* ``KEYWORD_SCHEDULE`` — 각 페어의 priority tier + slot + max articles per run.
  10분 슬롯 기반 파이프라인 스케줄러를 구동.

Notes:
  * 오타 보정됨: "Schneider Electir" → "Schneider Electric",
    "Anthrophic" → "Anthropic", "openAI" → "OpenAI"
  * 회사 리스트 없는 sub_keyword(탄소배출권, 교육장비)는 키워드 텍스트로 폴백.
"""
from __future__ import annotations

# Industry → sub-keyword → companies. Tickers will be filled in lazily
# by the SEC ticker resolver. Country is best-effort.
INDUSTRY_COMPANIES: list[tuple[str, str, list[tuple[str, str | None]]]] = [
    # (industry_ko, sub_keyword_ko, [(company_name, country?), ...])

    # IT기술
    ("IT기술", "보안", [
        ("Cisco Systems", "US"), ("Palo Alto Networks", "US"),
        ("CrowdStrike Holdings", "US"), ("Fortinet", "US"),
        ("Cloudflare", "US"), ("Motorola Solutions", "US"),
        ("VeriSign", "US"), ("Zscaler", "US"), ("F5", "US"),
    ]),
    ("IT기술", "소프트웨어", [
        ("Google", "US"), ("Apple", "US"), ("Microsoft", "US"),
        ("Oracle", "US"), ("Palantir", "US"), ("IBM", "US"),
        ("Palo Alto Networks", "US"), ("SAP", "DE"),
        ("Schneider Electric", "FR"),  # corrected from "Electir"
        ("CrowdStrike", "US"),
    ]),
    ("IT기술", "양자컴퓨터", [
        ("IonQ", "US"), ("Rigetti Computing", "US"),
        ("D-Wave Quantum", "CA"), ("Quantum Computing Inc", "US"),
        ("IBM", "US"), ("Microsoft", "US"), ("Google Quantum AI", "US"),
        ("Amazon Braket", "US"), ("Quantinuum", "US"), ("NVIDIA", "US"),
    ]),
    ("IT기술", "인공지능", [
        ("Google AI", "US"), ("Google DeepMind", "GB"), ("Gemini", "US"),
        ("NVIDIA", "US"), ("Microsoft AI", "US"), ("Microsoft Copilot", "US"),
        ("Azure AI", "US"), ("Amazon", "US"), ("Meta Platforms", "US"),
        ("Broadcom", "US"), ("Taiwan Semiconductor", "TW"), ("TSMC", "TW"),
        ("AMD", "US"),
        ("Anthropic", "US"),  # corrected from "Anthrophic"
        ("OpenAI", "US"),     # corrected from "openAI"
        ("Oracle AI", "US"), ("Palantir", "US"),
    ]),
    ("IT기술", "인터넷", [
        ("Google", "US"), ("Alphabet", "US"), ("Amazon", "US"),
        ("Meta", "US"), ("Instagram", "US"), ("Tencent", "CN"),
        ("Alibaba", "CN"), ("Netflix", "US"), ("Booking Holdings", "US"),
        ("Uber", "US"), ("Airbnb", "US"), ("Spotify", "SE"),
    ]),
    ("IT기술", "클라우드", [
        ("Amazon Web Services", "US"), ("AWS", "US"),
        ("Microsoft Azure", "US"), ("Azure", "US"),
        ("Google Cloud", "US"), ("Oracle Cloud", "US"),
        ("Oracle Cloud Infrastructure", "US"), ("OCI", "US"),
        ("Alibaba Cloud", "CN"), ("Salesforce", "US"),
        ("ServiceNow", "US"), ("Snowflake", "US"),
        ("Cloudflare", "US"), ("IBM Cloud", "US"),
        ("Red Hat OpenShift", "US"),
    ]),
    ("IT기술", "IT솔루션 구축", [
        # Not in the source file under this exact label — keep empty so
        # the pipeline falls back to keyword-text collection.
    ]),

    # 화학
    ("화학", "비료와 농약", [
        ("Nutrien", "CA"), ("Mosaic", "US"), ("CF Industries", "US"),
        ("Corteva", "US"), ("FMC Corporation", "US"),
    ]),
    ("화학", "산업용 가스", [
        ("Linde", "GB"), ("Air Liquide", "FR"), ("Air Products", "US"),
        ("Nippon Sanso", "JP"), ("Messer", "DE"),
    ]),
    ("화학", "화학원료", [
        ("Dow", "US"), ("BASF", "DE"), ("LyondellBasell", "NL"),
        ("Eastman Chemical", "US"), ("Westlake", "US"),
    ]),
    ("화학", "화학제품", [
        ("DuPont", "US"), ("3M", "US"), ("Sherwin-Williams", "US"),
        ("PPG Industries", "US"), ("Ecolab", "US"),
    ]),

    # 화장품
    ("화장품", "화장품 브랜드", [
        ("L'Oréal", "FR"), ("Estée Lauder", "US"), ("Shiseido", "JP"),
        ("Beiersdorf", "DE"), ("Nivea", "DE"), ("Amorepacific", "KR"),
    ]),
    ("화장품", "화장품 제조", [
        ("Cosmax", "KR"), ("Kolmar Korea", "KR"), ("Intercos", "IT"),
        ("Cosmecca Korea", "KR"), ("Nihon Kolmar", "JP"),
    ]),

    # 통신
    ("통신", "이동통신사", [
        ("Verizon", "US"), ("AT&T", "US"), ("T-Mobile", "US"),
        ("Comcast", "US"), ("Xfinity", "US"),
    ]),
    ("통신", "통신장비", [
        ("Cisco", "US"), ("Qualcomm", "US"), ("Motorola Solutions", "US"),
        ("Juniper Networks", "US"),
    ]),

    # 탄소저감 — no companies, falls back to keyword text
    ("탄소저감", "탄소배출권", []),

    # 종이
    ("종이", "골판지", [
        ("International Paper", "US"), ("Packaging Corp of America", "US"),
        ("Smurfit Westrock", "US"), ("Graphic Packaging", "US"),
        ("Greif", "US"),
    ]),
    ("종이", "백판지", [
        ("Graphic Packaging", "US"), ("Clearwater Paper", "US"),
        ("International Paper", "US"), ("Smurfit Westrock", "US"),
        ("Packaging Corp of America", "US"),
    ]),

    # 조선
    ("조선", "조선기자재", [
        ("Caterpillar", "US"), ("Curtiss-Wright", "US"), ("Wabtec", "US"),
        ("GE Vernova", "US"), ("Honeywell", "US"),
    ]),
    ("조선", "조선사", [
        ("Huntington Ingalls Industries", "US"), ("General Dynamics", "US"),
        ("Fincantieri", "IT"), ("Hanwha Ocean", "KR"),
        ("HD Hyundai Heavy Industries", "KR"),
    ]),

    # 전자부품
    ("전자부품", "가전부품", [
        ("Amphenol", "US"), ("TE Connectivity", "CH"), ("Jabil", "US"),
        ("Flex", "US"), ("Corning", "US"),
    ]),

    # 전력에너지
    ("전력에너지", "신재생 에너지", [
        ("NextEra Energy", "US"), ("First Solar", "US"),
        ("Enphase Energy", "US"), ("SolarEdge", "US"),
        ("Brookfield Renewable", "US"),
    ]),
    ("전력에너지", "원자력 발전", [
        ("Constellation Energy", "US"), ("Vistra", "US"),
        ("Duke Energy", "US"), ("Cameco", "CA"), ("BWX Technologies", "US"),
    ]),
    ("전력에너지", "전기설비", [
        ("Eaton", "IE"), ("GE Vernova", "US"), ("Hubbell", "US"),
        ("Quanta Services", "US"), ("Emerson Electric", "US"),
    ]),
    ("전력에너지", "화력발전", [
        ("GE Vernova", "US"), ("Duke Energy", "US"),
        ("Southern Company", "US"), ("Vistra", "US"), ("NRG Energy", "US"),
    ]),

    # 자동차
    ("자동차", "수소차", [
        ("Toyota", "JP"), ("Hyundai Motor", "KR"), ("Honda", "JP"),
        ("Plug Power", "US"), ("Nikola", "US"),
    ]),
    ("자동차", "오토바이", [
        ("Harley-Davidson", "US"), ("Honda", "JP"), ("Yamaha Motor", "JP"),
        ("Polaris", "US"), ("BRP", "CA"),
    ]),
    ("자동차", "자동차부품", [
        ("Aptiv", "IE"), ("BorgWarner", "US"), ("Magna International", "CA"),
        ("Lear", "US"), ("Gentex", "US"),
    ]),
    ("자동차", "자동차브랜드", [
        ("Tesla", "US"), ("General Motors", "US"), ("Ford", "US"),
        ("Toyota", "JP"), ("Stellantis", "NL"),
    ]),
    ("자동차", "자동차유통", [
        ("AutoNation", "US"), ("CarMax", "US"), ("Lithia Motors", "US"),
        ("Penske Automotive", "US"), ("Group 1 Automotive", "US"),
    ]),
    ("자동차", "전기차", [
        ("Tesla", "US"), ("Rivian", "US"), ("Lucid", "US"),
        ("BYD", "CN"), ("Li Auto", "CN"),
    ]),
    ("자동차", "전기차 부품", [
        ("Aptiv", "IE"), ("ON Semiconductor", "US"), ("Wolfspeed", "US"),
        ("BorgWarner", "US"), ("TE Connectivity", "CH"),
    ]),

    # 의류
    ("의류", "섬유", [
        ("Lululemon", "US"), ("Nike", "US"), ("VF Corporation", "US"),
        ("Gildan", "CA"), ("Unifi", "US"),
    ]),
    ("의류", "의류 브랜드", [
        ("Nike", "US"), ("Lululemon", "US"), ("Ralph Lauren", "US"),
        ("Tapestry", "US"), ("VF Corporation", "US"),
    ]),
    ("의류", "의류제조", [
        ("Gildan", "CA"), ("Hanesbrands", "US"), ("Levi Strauss", "US"),
        ("Kontoor Brands", "US"), ("Under Armour", "US"),
    ]),

    # 의료
    ("의료", "의료기기", [
        ("Medtronic", "IE"), ("Abbott Laboratories", "US"), ("Stryker", "US"),
        ("Boston Scientific", "US"), ("Intuitive Surgical", "US"),
    ]),
    ("의료", "의료서비스", [
        ("UnitedHealth Group", "US"), ("HCA Healthcare", "US"),
        ("CVS Health", "US"), ("Elevance Health", "US"), ("Cigna", "US"),
    ]),
    ("의료", "제약", [
        ("Eli Lilly", "US"), ("Johnson & Johnson", "US"), ("Pfizer", "US"),
        ("Merck", "US"), ("Bristol Myers Squibb", "US"),
    ]),

    # 음식료
    ("음식료", "음식료", [
        ("Coca-Cola", "US"), ("PepsiCo", "US"), ("Mondelez", "US"),
        ("General Mills", "US"), ("Kraft Heinz", "US"),
    ]),

    # 유통
    ("유통", "대형마트", [
        ("Walmart", "US"), ("Costco", "US"), ("Target", "US"),
        ("Kroger", "US"), ("BJ's Wholesale", "US"),
    ]),
    ("유통", "면세점", [
        ("Avolta", "CH"), ("LVMH DFS", "FR"), ("Hotel Shilla", "KR"),
        ("Lotte Shopping", "KR"), ("China Tourism Group Duty Free", "CN"),
    ]),
    ("유통", "무역", [
        ("C.H. Robinson", "US"), ("Expeditors International", "US"),
        ("Kuehne+Nagel", "CH"), ("UPS", "US"), ("FedEx", "US"),
    ]),
    ("유통", "백화점", [
        ("Macy's", "US"), ("Nordstrom", "US"), ("Dillard's", "US"),
        ("Kohl's", "US"), ("Tapestry", "US"),
    ]),
    ("유통", "온라인쇼핑", [
        ("Amazon", "US"), ("Shopify", "CA"), ("eBay", "US"),
        ("Etsy", "US"), ("MercadoLibre", "AR"),
    ]),
    ("유통", "편의점", [
        ("Casey's General Stores", "US"), ("Murphy USA", "US"),
        ("Alimentation Couche-Tard", "CA"), ("Seven & i Holdings", "JP"),
        ("Walmart", "US"),
    ]),

    # 원유
    ("원유", "원유개발", [
        ("Exxon Mobil", "US"), ("Chevron", "US"), ("ConocoPhillips", "US"),
        ("EOG Resources", "US"), ("Occidental Petroleum", "US"),
    ]),
    ("원유", "원유정제", [
        ("Valero Energy", "US"), ("Marathon Petroleum", "US"),
        ("Phillips 66", "US"), ("HF Sinclair", "US"), ("Exxon Mobil", "US"),
    ]),

    # 운송
    ("운송", "물류", [
        ("UPS", "US"), ("FedEx", "US"), ("C.H. Robinson", "US"),
        ("XPO", "US"), ("Expeditors International", "US"),
    ]),
    ("운송", "해상운송", [
        ("Matson", "US"), ("ZIM Integrated Shipping", "IL"), ("Kirby", "US"),
        ("Costamare", "GR"), ("Danaos", "GR"),
    ]),
    ("운송", "드론", [
        ("AeroVironment", "US"), ("Joby Aviation", "US"),
        ("Archer Aviation", "US"), ("Amazon", "US"), ("Kratos Defense", "US"),
    ]),
    ("운송", "항공사", [
        ("Delta Air Lines", "US"), ("United Airlines", "US"),
        ("American Airlines", "US"), ("Southwest Airlines", "US"),
        ("Alaska Air", "US"),
    ]),
    ("운송", "철도", [
        ("Union Pacific", "US"), ("CSX", "US"), ("Norfolk Southern", "US"),
        ("Canadian Pacific Kansas City", "CA"),
        ("Canadian National Railway", "CA"),
    ]),

    # 엔터테인먼트
    ("엔터테인먼트", "광고", [
        ("The Trade Desk", "US"), ("Omnicom", "US"),
        ("Interpublic Group", "US"), ("WPP", "GB"), ("Publicis", "FR"),
    ]),
    ("엔터테인먼트", "동영상 플랫폼", [
        ("Netflix", "US"), ("YouTube", "US"), ("Walt Disney", "US"),
        ("Amazon Prime Video", "US"), ("Roku", "US"),
    ]),
    ("엔터테인먼트", "방송", [
        ("Comcast", "US"), ("Walt Disney", "US"), ("Fox Corporation", "US"),
        ("Paramount Global", "US"), ("Warner Bros. Discovery", "US"),
    ]),
    ("엔터테인먼트", "영화", [
        ("Walt Disney", "US"), ("Warner Bros. Discovery", "US"),
        ("Netflix", "US"), ("NBCUniversal", "US"), ("Lionsgate", "US"),
    ]),
    ("엔터테인먼트", "웹툰", [
        ("Naver Webtoon", "KR"), ("Kakao", "KR"), ("Tencent", "CN"),
        ("Bilibili", "CN"), ("Comixology", "US"),
    ]),
    ("엔터테인먼트", "음원", [
        ("Spotify", "SE"), ("Universal Music Group", "NL"),
        ("Warner Music Group", "US"), ("Apple Music", "US"),
        ("Tencent Music", "CN"),
    ]),
    ("엔터테인먼트", "출판", [
        ("Pearson", "GB"), ("News Corp", "US"), ("Scholastic", "US"),
        ("John Wiley & Sons", "US"), ("RELX", "GB"),
    ]),
    ("엔터테인먼트", "캐릭터", [
        ("Walt Disney", "US"), ("Hasbro", "US"), ("Mattel", "US"),
        ("Sanrio", "JP"), ("Nintendo", "JP"),
    ]),

    # 스마트폰
    ("스마트폰", "스마트폰 부품", [
        ("Qualcomm", "US"), ("Broadcom", "US"), ("Skyworks Solutions", "US"),
        ("Qorvo", "US"), ("Corning", "US"),
    ]),
    ("스마트폰", "스마트폰 제조", [
        ("Apple", "US"), ("Samsung Electronics", "KR"), ("Xiaomi", "CN"),
        ("Sony", "JP"), ("Motorola", "US"),
    ]),

    # 여행
    ("여행", "렌터카", [
        ("Hertz", "US"), ("Avis Budget", "US"), ("Enterprise Holdings", "US"),
        ("Uber", "US"), ("Lyft", "US"),
    ]),
    ("여행", "여행플랫폼", [
        ("Booking Holdings", "US"), ("Airbnb", "US"), ("Expedia", "US"),
        ("Trip.com", "CN"), ("Tripadvisor", "US"),
    ]),
    ("여행", "카지노", [
        ("Las Vegas Sands", "US"), ("MGM Resorts", "US"),
        ("Wynn Resorts", "US"), ("Caesars Entertainment", "US"),
        ("Penn Entertainment", "US"),
    ]),
    ("여행", "호텔과 리조트", [
        ("Marriott", "US"), ("Hilton", "US"), ("Hyatt", "US"),
        ("Wyndham", "US"), ("InterContinental Hotels", "GB"),
    ]),

    # 수자원
    ("수자원", "수자원", [
        ("American Water Works", "US"), ("Xylem", "US"),
        ("Essential Utilities", "US"), ("California Water Service", "US"),
        ("Pentair", "GB"),
    ]),

    # 배터리
    ("배터리", "배터리부품", [
        ("Albemarle", "US"), ("Arcadium Lithium", "US"),
        ("ON Semiconductor", "US"), ("TE Connectivity", "CH"),
        ("Amphenol", "US"),
    ]),
    ("배터리", "배터리소재", [
        ("Albemarle", "US"), ("Sociedad Quimica y Minera", "CL"),
        ("Arcadium Lithium", "US"), ("Lithium Americas", "US"),
        ("MP Materials", "US"),
    ]),
    ("배터리", "배터리장비", [
        ("Applied Materials", "US"), ("Enovix", "US"),
        ("Rockwell Automation", "US"), ("Emerson Electric", "US"),
        ("Honeywell", "US"),
    ]),
    ("배터리", "배터리제조", [
        ("Tesla", "US"), ("Panasonic", "JP"), ("LG Energy Solution", "KR"),
        ("Samsung SDI", "KR"), ("CATL", "CN"),
    ]),
    ("배터리", "폐배터리 재활용", [
        ("Li-Cycle", "CA"), ("Redwood Materials", "US"),
        ("American Battery Technology", "US"), ("Umicore", "BE"),
        ("Glencore", "CH"),
    ]),

    # 반도체
    ("반도체", "반도체 부품소재", [
        ("Applied Materials", "US"), ("Entegris", "US"), ("KLA", "US"),
        ("DuPont", "US"), ("Corning", "US"),
    ]),
    ("반도체", "반도체 장비", [
        ("ASML", "NL"), ("Applied Materials", "US"), ("Lam Research", "US"),
        ("KLA", "US"), ("Teradyne", "US"),
    ]),
    ("반도체", "반도체 파운드리", [
        ("Taiwan Semiconductor Manufacturing", "TW"), ("GlobalFoundries", "US"),
        ("Intel", "US"), ("Samsung Electronics", "KR"),
        ("United Microelectronics", "TW"),
    ]),
    ("반도체", "반도체 패키징", [
        ("Amkor Technology", "US"), ("ASE Technology", "TW"), ("Intel", "US"),
        ("TSMC", "TW"), ("Advanced Micro Devices", "US"),
    ]),
    ("반도체", "반도체 팹리스", [
        ("NVIDIA", "US"), ("AMD", "US"), ("Qualcomm", "US"),
        ("Broadcom", "US"), ("Marvell Technology", "US"),
    ]),
    ("반도체", "종합반도체", [
        ("Intel", "US"), ("Texas Instruments", "US"), ("Analog Devices", "US"),
        ("Micron Technology", "US"), ("Samsung Electronics", "KR"),
    ]),

    # 방위산업물자
    ("방위산업물자", "방위산업", [
        ("Lockheed Martin", "US"), ("RTX", "US"), ("Northrop Grumman", "US"),
        ("General Dynamics", "US"), ("L3Harris Technologies", "US"),
    ]),

    # 생활용품
    ("생활용품", "그릇", [
        ("Newell Brands", "US"), ("Lifetime Brands", "US"),
        ("Williams-Sonoma", "US"), ("Whirlpool", "US"),
        ("Steelite International", "GB"),
    ]),
    ("생활용품", "마스크", [
        ("3M", "US"), ("Honeywell", "US"), ("Kimberly-Clark", "US"),
        ("Cardinal Health", "US"), ("Owens & Minor", "US"),
    ]),

    # 바이오
    ("바이오", "바이오서비스", [
        ("Thermo Fisher Scientific", "US"), ("Danaher", "US"),
        ("Charles River Laboratories", "US"), ("IQVIA", "US"), ("Labcorp", "US"),
    ]),
    ("바이오", "바이오시밀러", [
        ("Amgen", "US"), ("Pfizer", "US"), ("Biogen", "US"),
        ("Celltrion", "KR"), ("Samsung Biologics", "KR"),
    ]),
    ("바이오", "바이오신약", [
        ("Regeneron", "US"), ("Vertex Pharmaceuticals", "US"), ("Moderna", "US"),
        ("Gilead Sciences", "US"), ("Alnylam Pharmaceuticals", "US"),
    ]),

    # 리츠
    ("리츠", "상업용 리츠", [
        ("Simon Property Group", "US"), ("Realty Income", "US"),
        ("Federal Realty", "US"), ("Kimco Realty", "US"),
        ("Brixmor Property", "US"),
    ]),
    ("리츠", "오피스 리츠", [
        ("Boston Properties", "US"), ("Kilroy Realty", "US"),
        ("SL Green Realty", "US"), ("Cousins Properties", "US"),
        ("Vornado Realty Trust", "US"),
    ]),
    ("리츠", "인프라 리츠", [
        ("American Tower", "US"), ("Crown Castle", "US"),
        ("SBA Communications", "US"), ("Equinix", "US"), ("Digital Realty", "US"),
    ]),
    ("리츠", "주거용 리츠", [
        ("Equity Residential", "US"), ("AvalonBay Communities", "US"),
        ("Invitation Homes", "US"), ("Camden Property Trust", "US"),
        ("Essex Property Trust", "US"),
    ]),

    # 디스플레이
    ("디스플레이", "디스플레이 부품소재", [
        ("Corning", "US"), ("Universal Display", "US"),
        ("Applied Materials", "US"), ("DuPont", "US"), ("3M", "US"),
    ]),
    ("디스플레이", "디스플레이 장비", [
        ("Applied Materials", "US"), ("KLA", "US"), ("Lam Research", "US"),
        ("Coherent", "US"), ("Teradyne", "US"),
    ]),
    ("디스플레이", "디스플레이 패널", [
        ("Samsung Electronics", "KR"), ("LG Display", "KR"),
        ("BOE Technology", "CN"), ("AUO", "TW"), ("Innolux", "TW"),
    ]),
    ("디스플레이", "LED", [
        ("Wolfspeed", "US"), ("ams OSRAM", "AT"), ("Signify", "NL"),
        ("Acuity Brands", "US"), ("Universal Display", "US"),
    ]),

    # 기계
    ("기계", "농업용 기계", [
        ("Deere", "US"), ("AGCO", "US"), ("CNH Industrial", "GB"),
        ("Caterpillar", "US"), ("Kubota", "JP"),
    ]),
    ("기계", "로봇", [
        ("Rockwell Automation", "US"), ("Teradyne", "US"),
        ("Zebra Technologies", "US"), ("ABB", "CH"), ("Intuitive Surgical", "US"),
    ]),
    ("기계", "산업용 기계", [
        ("Caterpillar", "US"), ("Deere", "US"), ("Illinois Tool Works", "US"),
        ("Parker-Hannifin", "US"), ("Emerson Electric", "US"),
    ]),

    # 농업
    ("농업", "농업", [
        ("Deere", "US"), ("Archer-Daniels-Midland", "US"), ("Bunge", "US"),
        ("Nutrien", "CA"), ("Corteva", "US"),
    ]),

    # 금융
    ("금융", "결제서비스", [
        ("Visa", "US"), ("Mastercard", "US"), ("PayPal", "US"),
        ("Block", "US"), ("Fiserv", "US"),
    ]),
    ("금융", "금융그룹", [
        ("JPMorgan Chase", "US"), ("Bank of America", "US"),
        ("Citigroup", "US"), ("Wells Fargo", "US"), ("Morgan Stanley", "US"),
    ]),
    ("금융", "금융기기", [
        ("NCR Atleos", "US"), ("Diebold Nixdorf", "US"), ("Fiserv", "US"),
        ("Global Payments", "US"), ("Jack Henry", "US"),
    ]),
    ("금융", "금융상품거래소", [
        ("CME Group", "US"), ("Intercontinental Exchange", "US"),
        ("Nasdaq", "US"), ("Cboe Global Markets", "US"), ("MarketAxess", "US"),
    ]),
    ("금융", "벤처캐피탈", [
        ("Blackstone", "US"), ("KKR", "US"), ("Apollo Global Management", "US"),
        ("Ares Management", "US"), ("Carlyle Group", "US"),
    ]),
    ("금융", "보험", [
        ("Berkshire Hathaway", "US"), ("Progressive", "US"), ("Chubb", "CH"),
        ("Aflac", "US"), ("MetLife", "US"),
    ]),
    ("금융", "신용평가", [
        ("Moody's", "US"), ("S&P Global", "US"), ("Fitch Ratings", "US"),
        ("TransUnion", "US"), ("Equifax", "US"),
    ]),
    ("금융", "암호화폐", [
        ("Coinbase", "US"), ("MicroStrategy", "US"), ("Riot Platforms", "US"),
        ("Marathon Digital", "US"), ("Robinhood", "US"),
    ]),
    ("금융", "은행", [
        ("JPMorgan Chase", "US"), ("Bank of America", "US"),
        ("Wells Fargo", "US"), ("Citigroup", "US"), ("U.S. Bancorp", "US"),
    ]),
    ("금융", "증권", [
        ("Charles Schwab", "US"), ("Morgan Stanley", "US"),
        ("Goldman Sachs", "US"), ("Interactive Brokers", "US"),
        ("Robinhood", "US"),
    ]),
    ("금융", "카드", [
        ("Visa", "US"), ("Mastercard", "US"), ("American Express", "US"),
        ("Discover Financial", "US"), ("Capital One", "US"),
    ]),

    # 금속
    ("금속", "광산개발", [
        ("Freeport-McMoRan", "US"), ("Rio Tinto", "GB"), ("BHP", "AU"),
        ("Vale", "BR"), ("Newmont", "US"),
    ]),
    ("금속", "구리", [
        ("Freeport-McMoRan", "US"), ("Southern Copper", "US"),
        ("Rio Tinto", "GB"), ("BHP", "AU"), ("Teck Resources", "CA"),
    ]),
    ("금속", "아연", [
        ("Teck Resources", "CA"), ("Glencore", "CH"), ("Nyrstar", "BE"),
        ("Hindustan Zinc", "IN"), ("South32", "AU"),
    ]),
    ("금속", "알루미늄", [
        ("Alcoa", "US"), ("Rio Tinto", "GB"), ("Norsk Hydro", "NO"),
        ("Century Aluminum", "US"), ("Kaiser Aluminum", "US"),
    ]),
    ("금속", "철강", [
        ("Nucor", "US"), ("Steel Dynamics", "US"), ("U.S. Steel", "US"),
        ("Cleveland-Cliffs", "US"), ("ArcelorMittal", "LU"),
    ]),

    # 교육
    ("교육", "교육서비스", [
        ("Duolingo", "US"), ("Coursera", "US"), ("Grand Canyon Education", "US"),
        ("Chegg", "US"), ("Stride", "US"),
    ]),
    ("교육", "교육장비", []),  # source had no list; fallback to keyword text
    ("교육", "교육출판", [
        ("Pearson", "GB"), ("Scholastic", "US"), ("John Wiley & Sons", "US"),
        ("McGraw Hill", "US"), ("RELX", "GB"),
    ]),
]


# ---------------------------------------------------------------------------
# Priority-tier scheduling (from pipeline_schedule_prompt.txt)
# ---------------------------------------------------------------------------
# (industry_ko, sub_keyword_ko, priority, interval_min, max_articles, slot_min)
KEYWORD_SCHEDULE: list[tuple[str, str, str, int, int, int]] = [
    # ----- 00분 슬롯 -----
    ("IT기술", "인공지능",      "P0", 10, 5, 0),
    ("IT기술", "클라우드",      "P0", 10, 5, 0),
    ("IT기술", "보안",          "P0", 20, 5, 0),
    ("IT기술", "소프트웨어",    "P0", 20, 5, 0),
    ("IT기술", "인터넷",        "P1", 30, 4, 0),
    ("IT기술", "양자컴퓨터",    "P1", 30, 4, 0),
    ("IT기술", "IT솔루션 구축", "P2", 60, 3, 0),

    ("반도체", "반도체 장비",     "P0", 10, 5, 0),
    ("반도체", "반도체 파운드리", "P0", 10, 5, 0),
    ("반도체", "반도체 팹리스",   "P0", 10, 5, 0),
    ("반도체", "종합반도체",      "P0", 20, 5, 0),
    ("반도체", "반도체 부품소재", "P1", 30, 4, 0),
    ("반도체", "반도체 패키징",   "P1", 30, 4, 0),

    ("배터리", "배터리제조",      "P0", 20, 5, 0),
    ("배터리", "배터리소재",      "P0", 20, 5, 0),
    ("배터리", "배터리부품",      "P1", 30, 4, 0),
    ("배터리", "배터리장비",      "P1", 30, 4, 0),
    ("배터리", "폐배터리 재활용", "P1", 30, 4, 0),

    # ----- 10분 슬롯 -----
    ("자동차", "전기차",         "P0", 20, 5, 10),
    ("자동차", "전기차 부품",    "P0", 20, 5, 10),
    ("자동차", "자동차브랜드",   "P1", 30, 4, 10),
    ("자동차", "자동차부품",     "P1", 30, 4, 10),
    ("자동차", "수소차",         "P1", 30, 4, 10),
    ("자동차", "자동차유통",     "P2", 60, 3, 10),
    ("자동차", "오토바이",       "P3", 60, 2, 10),

    ("전력에너지", "원자력 발전",  "P0", 20, 5, 10),
    ("전력에너지", "신재생 에너지","P0", 20, 5, 10),
    ("전력에너지", "전기설비",     "P1", 30, 4, 10),
    ("전력에너지", "화력발전",     "P1", 30, 4, 10),

    ("원유", "원유개발", "P0", 20, 5, 10),
    ("원유", "원유정제", "P0", 20, 5, 10),

    ("방위산업물자", "방위산업", "P0", 20, 5, 10),

    # ----- 20분 슬롯 -----
    ("금융", "은행",           "P0", 20, 5, 20),
    ("금융", "증권",           "P0", 20, 5, 20),
    ("금융", "암호화폐",       "P0", 10, 5, 20),
    ("금융", "금융상품거래소", "P1", 30, 4, 20),
    ("금융", "결제서비스",     "P1", 30, 4, 20),
    ("금융", "카드",           "P1", 30, 4, 20),
    ("금융", "보험",           "P1", 30, 4, 20),
    ("금융", "금융그룹",       "P1", 30, 4, 20),
    ("금융", "벤처캐피탈",     "P2", 60, 3, 20),
    ("금융", "신용평가",       "P2", 60, 3, 20),
    ("금융", "금융기기",       "P3", 60, 2, 20),

    ("의료", "제약",       "P0", 20, 5, 20),
    ("의료", "의료기기",   "P1", 30, 4, 20),
    ("의료", "의료서비스", "P1", 30, 4, 20),

    ("바이오", "바이오신약",   "P0", 20, 5, 20),
    ("바이오", "바이오시밀러", "P1", 30, 4, 20),
    ("바이오", "바이오서비스", "P1", 30, 4, 20),

    # ----- 30분 슬롯 -----
    ("통신", "이동통신사", "P1", 30, 4, 30),
    ("통신", "통신장비",   "P1", 30, 4, 30),

    ("운송", "항공사",     "P1", 30, 4, 30),
    ("운송", "해상운송",   "P1", 30, 4, 30),
    ("운송", "물류",       "P1", 30, 4, 30),
    ("운송", "철도",       "P2", 60, 3, 30),
    ("운송", "드론",       "P1", 30, 4, 30),

    ("조선", "조선사",     "P1", 30, 4, 30),
    ("조선", "조선기자재", "P2", 60, 3, 30),

    ("기계", "산업용 기계", "P2", 60, 3, 30),
    ("기계", "로봇",        "P1", 30, 4, 30),
    ("기계", "농업용 기계", "P2", 60, 3, 30),

    ("전자부품", "가전부품",    "P2", 60, 3, 30),
    ("스마트폰", "스마트폰 제조","P1", 30, 4, 30),
    ("스마트폰", "스마트폰 부품","P1", 30, 4, 30),

    # ----- 40분 슬롯 -----
    ("화학", "비료와 농약", "P1", 30, 4, 40),
    ("화학", "산업용 가스", "P1", 30, 4, 40),
    ("화학", "화학원료",    "P2", 60, 3, 40),
    ("화학", "화학제품",    "P2", 60, 3, 40),

    ("금속", "구리",       "P1", 30, 4, 40),
    ("금속", "알루미늄",   "P1", 30, 4, 40),
    ("금속", "철강",       "P1", 30, 4, 40),
    ("금속", "광산개발",   "P1", 30, 4, 40),
    ("금속", "아연",       "P2", 60, 3, 40),

    ("탄소저감", "탄소배출권", "P1", 30, 4, 40),

    ("디스플레이", "디스플레이 패널",     "P2", 60, 3, 40),
    ("디스플레이", "디스플레이 장비",     "P2", 60, 3, 40),
    ("디스플레이", "디스플레이 부품소재", "P2", 60, 3, 40),
    ("디스플레이", "LED",                 "P2", 60, 3, 40),

    ("종이", "골판지", "P3", 60, 2, 40),
    ("종이", "백판지", "P3", 60, 2, 40),

    ("수자원", "수자원", "P2", 60, 3, 40),
    ("농업",   "농업",   "P2", 60, 3, 40),

    # ----- 50분 슬롯 -----
    ("유통", "온라인쇼핑", "P1", 30, 4, 50),
    ("유통", "대형마트",   "P2", 60, 3, 50),
    ("유통", "편의점",     "P2", 60, 3, 50),
    ("유통", "백화점",     "P2", 60, 3, 50),
    ("유통", "무역",       "P2", 60, 3, 50),
    ("유통", "면세점",     "P3", 60, 2, 50),

    ("음식료", "음식료", "P2", 60, 3, 50),

    ("화장품", "화장품 브랜드", "P2", 60, 3, 50),
    ("화장품", "화장품 제조",   "P2", 60, 3, 50),

    ("의류", "의류 브랜드", "P2", 60, 3, 50),
    ("의류", "의류제조",    "P3", 60, 2, 50),
    ("의류", "섬유",        "P3", 60, 2, 50),

    ("생활용품", "마스크", "P3", 60, 2, 50),
    ("생활용품", "그릇",   "P3", 60, 1, 50),

    ("여행", "여행플랫폼",   "P1", 30, 4, 50),
    ("여행", "호텔과 리조트","P2", 60, 3, 50),
    ("여행", "카지노",       "P2", 60, 3, 50),
    ("여행", "렌터카",       "P3", 60, 2, 50),

    ("엔터테인먼트", "동영상 플랫폼", "P1", 30, 4, 50),
    ("엔터테인먼트", "음원",          "P1", 30, 4, 50),
    ("엔터테인먼트", "방송",          "P2", 60, 3, 50),
    ("엔터테인먼트", "영화",          "P2", 60, 3, 50),
    ("엔터테인먼트", "광고",          "P2", 60, 3, 50),
    ("엔터테인먼트", "웹툰",          "P3", 60, 2, 50),
    ("엔터테인먼트", "출판",          "P3", 60, 2, 50),
    ("엔터테인먼트", "캐릭터",        "P3", 60, 2, 50),

    ("리츠", "인프라 리츠",   "P1", 30, 4, 50),
    ("리츠", "상업용 리츠",   "P2", 60, 3, 50),
    ("리츠", "오피스 리츠",   "P2", 60, 3, 50),
    ("리츠", "주거용 리츠",   "P2", 60, 3, 50),

    ("교육", "교육서비스", "P2", 60, 3, 50),
    ("교육", "교육장비",   "P3", 60, 1, 50),
    ("교육", "교육출판",   "P3", 60, 2, 50),
]
