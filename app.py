import streamlit as st
import streamlit.components.v1 as components
import json

# 1. 페이지 기본 설정 (전체 화면 사용)
st.set_page_config(
    page_title="2026 ktMOS북부 설 맞이 클린캠페인",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# [필수 수정] 여기에 본인의 Firebase 설정값을 복사해서 붙여넣으세요.
# (Firebase 콘솔 -> 프로젝트 설정 -> 일반 -> 내 앱 -> SDK 설정 및 구성 에서 복사)
# ==============================================================================
firebase_config = {
   apiKey: "AIzaSyBlEUW6VQQAR3gojzHqDqoWFSSz4Za-7yw",
  authDomain: "clean-campaign-2026.firebaseapp.com",
  projectId: "clean-campaign-2026",
  storageBucket: "clean-campaign-2026.firebasestorage.app",
  messagingSenderId: "55496851514",
  appId: "1:55496851514:web:7e1cd4a0352500a7df7503",
  measurementId: "G-VCBNRC2BYR"
}
# ==============================================================================

# Python 딕셔너리를 JSON 문자열로 변환 (HTML에 주입하기 위함)
firebase_config_str = json.dumps(firebase_config)

# 2. 리액트(React) 웹페이지 코드 (HTML/JS)
# 주의: 파이썬 f-string 안에서는 중괄호 {}를 두 번 {{}} 써야 JavaScript 문법으로 인식됩니다.
html_code = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clean Campaign</title>
    
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />

    <style>
        body {{ font-family: 'Pretendard', sans-serif; background-color: #020617; color: white; margin: 0; padding: 0; overflow-x: hidden; }}
        
        /* 애니메이션 정의 */
        @keyframes fade-in-up {{ from {{ opacity: 0; transform: translateY(30px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @keyframes scale-in {{ from {{ opacity: 0; transform: scale(0.95); }} to {{ opacity: 1; transform: scale(1); }} }}
        @keyframes scan {{ 0% {{ transform: translateY(-100%); opacity: 0; }} 50% {{ opacity: 1; }} 100% {{ transform: translateY(100%); opacity: 0; }} }}
        @keyframes float {{ 0% {{ transform: translateY(0px); }} 50% {{ transform: translateY(-10px); }} 100% {{ transform: translateY(0px); }} }}
        
        .animate-fade-in-up {{ animation: fade-in-up 1.2s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; }}
        .animate-scale-in {{ animation: scale-in 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }}
        .animate-scan {{ animation: scan 2s infinite linear; }}
        .animate-float {{ animation: float 3s ease-in-out infinite; }}
        
        .glass-panel {{
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .custom-alert {{
            position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
            z-index: 9999; animation: fade-in-up 0.3s ease-out forwards;
        }}
        /* 스크롤바 커스텀 */
        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: #0f172a; }}
        ::-webkit-scrollbar-thumb {{ background: #ef4444; border-radius: 10px; }}
    </style>
</head>
<body>
    <div id="root"></div>

    <script type="module">
        import {{ initializeApp }} from "https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js";
        import {{ getAuth, signInAnonymously, onAuthStateChanged }} from "https://www.gstatic.com/firebasejs/11.6.1/firebase-auth.js";
        import {{ getFirestore, collection, addDoc, onSnapshot }} from "https://www.gstatic.com/firebasejs/11.6.1/firebase-firestore.js";

        window.FirebaseSDK = {{ 
            initializeApp, getAuth, signInAnonymously, 
            onAuthStateChanged, getFirestore, collection, addDoc, onSnapshot
        }};
    </script>

    <script type="text/babel">
        // Python에서 주입한 설정값 사용
        const firebaseConfig = {firebase_config_str};
        const appId = 'ktmos-clean-2026';

        const {{ useState, useEffect, useRef }} = React;

        // 아이콘 컴포넌트
        const Icon = ({{ name, size = 24, className = "" }}) => {{
            useEffect(() => {{ if (window.lucide) window.lucide.createIcons(); }}, [name]);
            return <i data-lucide={{name}} style={{{{ width: size, height: size }}}} className={{className}}></i>;
        }};

        const App = () => {{
            const [user, setUser] = useState(null);
            const [empId, setEmpId] = useState('');
            const [empName, setEmpName] = useState('');
            const [isPledged, setIsPledged] = useState(false);
            const [isMuted, setIsMuted] = useState(true);
            const [videoSrc, setVideoSrc] = useState("https://assets.mixkit.co/videos/preview/mixkit-abstract-red-and-white-flow-2336-large.mp4");
            const [pledges, setPledges] = useState([]);
            const [displayRate, setDisplayRate] = useState(0);
            const [isScanning, setIsScanning] = useState(false);
            const [scanResult, setScanResult] = useState(null);
            const [selectedGoal, setSelectedGoal] = useState('');
            const [alertMsg, setAlertMsg] = useState('');
            const videoRef = useRef(null);
            const TOTAL_EMPLOYEES = 500;

            // 운세 DB
            const fortuneDB = {{
                growth: [
                    {{ slogan: "투명한 도약, 붉은 말처럼 거침없이 성장하는 한 해", fortune: "올해 당신의 청렴 에너지는 99%! 투명한 업무 처리가 곧 당신의 독보적인 커리어가 됩니다." }},
                    {{ slogan: "정직이라는 박차를 가해 더 높은 곳으로 질주하세요", fortune: "거짓 없는 성장이 가장 빠른 길입니다. 주변의 두터운 신뢰가 당신의 든든한 날개가 될 것입니다." }}
                ],
                happiness: [
                    {{ slogan: "떳떳한 마음이 선사하는 가장 따뜻한 행복의 해", fortune: "가족에게 부끄럽지 않은 당신의 정직함이 집안의 평안과 웃음꽃을 불러옵니다." }},
                    {{ slogan: "깨끗한 소통으로 피어나는 동료 간의 진정한 즐거움", fortune: "작은 호의보다 큰 진심이 통하는 한 해입니다. 사람 사이의 신뢰가 최고의 행운입니다." }}
                ],
                challenge: [
                    {{ slogan: "청렴의 가치를 지키며 한계를 넘어 질주하는 2026", fortune: "어려운 순간에도 원칙을 지키는 모습이 동료들에게 가장 큰 영감이 될 것입니다." }},
                    {{ slogan: "정직한 도전은 결코 멈추지 않는 붉은 말과 같습니다", fortune: "타협하지 않는 용기가 당신을 독보적인 전문가로 만들어주는 결정적 한 해가 됩니다." }}
                ]
            }};

            // Firebase 초기화
            useEffect(() => {{
                const initAuth = async () => {{
                    if (!window.FirebaseSDK) {{ setTimeout(initAuth, 500); return; }}
                    const {{ initializeApp, getAuth, signInAnonymously, onAuthStateChanged }} = window.FirebaseSDK;
                    
                    try {{
                        let app;
                        try {{ app = initializeApp(firebaseConfig); }} catch(e) {{}} 
                        const auth = getAuth();
                        await signInAnonymously(auth);
                        onAuthStateChanged(auth, setUser);
                    }} catch (e) {{
                        console.error("Firebase Auth Error", e);
                        if(e.code === 'auth/invalid-api-key') showAlert("설정 오류: API Key를 확인하세요.");
                    }}
                }};
                initAuth();
            }}, []);

            // 실시간 데이터 수신
            useEffect(() => {{
                if (!user || !window.FirebaseSDK) return;
                const {{ getFirestore, collection, onSnapshot }} = window.FirebaseSDK;
                const db = getFirestore();
                const pledgeCol = collection(db, 'artifacts', appId, 'public', 'data', 'pledges');
                
                const unsubscribe = onSnapshot(pledgeCol, (snapshot) => {{
                    setPledges(snapshot.docs.map(doc => doc.data()));
                }});
                return () => unsubscribe();
            }}, [user]);

            // 프로그레스바 애니메이션
            useEffect(() => {{
                if (isPledged || pledges.length > 0) {{
                    const targetRate = Math.min(100, (pledges.length / TOTAL_EMPLOYEES) * 100);
                    let start = 0;
                    const timer = setInterval(() => {{
                        start += (targetRate / 60);
                        if (start >= targetRate) {{
                            setDisplayRate(targetRate.toFixed(1));
                            clearInterval(timer);
                        }} else {{
                            setDisplayRate(start.toFixed(1));
                        }}
                    }}, 20);
                    return () => clearInterval(timer);
                }}
            }}, [isPledged, pledges.length]);

            const showAlert = (msg) => {{
                setAlertMsg(msg);
                setTimeout(() => setAlertMsg(''), 4000);
            }};

            const fireFireworks = () => {{
                const end = Date.now() + 3000;
                const frame = () => {{
                    confetti({{ particleCount: 5, angle: 60, spread: 55, origin: {{ x: 0 }}, colors: ['#ff0000', '#ffd700'] }});
                    confetti({{ particleCount: 5, angle: 120, spread: 55, origin: {{ x: 1 }}, colors: ['#ff0000', '#ffd700'] }});
                    if (Date.now() < end) requestAnimationFrame(frame);
                }};
                frame();
            }};

            const handlePledgeSubmit = async (e) => {{
                e.preventDefault();
                if (!user) {{ showAlert("서버 연결 중입니다..."); return; }}
                if (!empId || !empName) return;
                
                if (pledges.some(p => p.empId === empId)) {{
                    showAlert(`${{empName}}님은 이미 참여하셨습니다.`);
                    setIsPledged(true);
                    return;
                }}

                const {{ getFirestore, collection, addDoc }} = window.FirebaseSDK;
                const db = getFirestore();
                try {{
                    await addDoc(collection(db, 'artifacts', appId, 'public', 'data', 'pledges'), {{
                        empId, empName, timestamp: Date.now(), uid: user.uid
                    }});
                    setIsPledged(true);
                    fireFireworks();
                }} catch (err) {{ showAlert("저장 실패: 권한이 없거나 설정 오류입니다."); }}
            }};

            const runAIScan = () => {{
                if (!empName || !selectedGoal) {{ showAlert("정보를 입력해주세요."); return; }}
                setIsScanning(true);
                setScanResult(null);
                setTimeout(() => {{
                    const options = fortuneDB[selectedGoal];
                    setScanResult(options[Math.floor(Math.random() * options.length)]);
                    setIsScanning(false);
                }}, 2000);
            }};

            const handleVideoUpload = (e) => {{
                const file = e.target.files[0];
                if (file) setVideoSrc(URL.createObjectURL(file));
            }};

            return (
                <div className="min-h-screen text-slate-100">
                    {{alertMsg && (
                        <div className="custom-alert bg-red-600 text-white px-6 py-3 rounded-2xl shadow-xl font-bold flex items-center gap-2">
                             {{alertMsg}}
                        </div>
                    )}}

                    {{/* Hero Section */}}
                    <section className="relative h-screen flex flex-col items-center justify-center text-center px-6 overflow-hidden">
                        <video ref={{videoRef}} className="absolute top-0 left-0 w-full h-full object-cover opacity-40 z-0" autoPlay muted loop playsInline src={{videoSrc}}></video>
                        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-transparent to-slate-950 z-[1]"></div>
                        
                        <div className="z-10 animate-fade-in-up max-w-5xl">
                            <div className="inline-block px-4 py-1.5 rounded-full bg-red-600/20 border border-red-600/30 text-red-500 font-bold text-sm tracking-widest mb-6 animate-pulse">
                                2026 병오년(丙午年) : 붉은 말의 해
                            </div>
                            <h1 className="text-6xl md:text-9xl font-black mb-6 tracking-tighter leading-[0.9] italic">
                                새해 복 <br/> <span className="text-red-600">많이 받으십시오</span>
                            </h1>
                            <p className="text-xl md:text-2xl text-slate-300 font-medium max-w-3xl mx-auto leading-relaxed mb-12">
                                ktMOS북부 임직원 여러분, 정직과 신뢰를 바탕으로 <br className="hidden md:block"/>
                                더 크게 도약하고 성장하는 2026년이 되시길 기원합니다.
                            </p>
                            <div className="flex flex-wrap justify-center gap-4">
                                <a href="#campaign" className="px-10 py-4 bg-red-600 text-white font-black rounded-2xl hover:bg-red-500 transition-all shadow-[0_0_30px_rgba(220,38,38,0.4)] hover:scale-105">캠페인 확인하기</a>
                                <button onClick={{() => {{ videoRef.current.muted = !videoRef.current.muted; setIsMuted(!isMuted); }}}} className="p-4 bg-white/10 border border-white/20 rounded-2xl backdrop-blur-md hover:bg-white/20 transition-all">
                                    <Icon name={{isMuted ? "volume-x" : "volume-2"}} />
                                </button>
                                <label className="p-4 bg-white/10 border border-white/20 rounded-2xl backdrop-blur-md hover:bg-white/20 transition-all cursor-pointer">
                                    <Icon name="upload" />
                                    <input type="file" className="hidden" accept="video/*" onChange={{handleVideoUpload}} />
                                </label>
                            </div>
                        </div>
                    </section>

                    {{/* AI Aura Scanner */}}
                    <section className="py-24 px-6 relative overflow-hidden">
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-red-600/10 rounded-full blur-[120px]"></div>
                        <div className="max-w-4xl mx-auto text-center relative z-10">
                            <h2 className="text-4xl md:text-5xl font-black mb-16 tracking-tight">2026 청렴 아우라 분석</h2>
                            <div className="glass-panel p-8 md:p-12 rounded-[3rem] shadow-2xl">
                                <div className="grid md:grid-cols-2 gap-4 mb-8">
                                    <input type="text" value={{empName}} onChange={{e => setEmpName(e.target.value)}} placeholder="성함" className="w-full px-6 py-4 bg-slate-900/50 border border-white/10 rounded-2xl focus:ring-2 focus:ring-red-600 outline-none font-bold text-center text-white"/>
                                    <select value={{selectedGoal}} onChange={{e => setSelectedGoal(e.target.value)}} className="w-full px-6 py-4 bg-slate-900/50 border border-white/10 rounded-2xl focus:ring-2 focus:ring-red-600 outline-none font-bold text-center appearance-none cursor-pointer text-white">
                                        <option value="" className="text-black">올해의 주요 목표</option>
                                        <option value="growth" className="text-black">지속적인 성장</option>
                                        <option value="happiness" className="text-black">가족의 행복</option>
                                        <option value="challenge" className="text-black">새로운 도전</option>
                                    </select>
                                </div>
                                <button onClick={{runAIScan}} disabled={{isScanning}} className="w-full py-5 bg-gradient-to-r from-red-600 to-orange-600 rounded-2xl font-black text-xl hover:opacity-90 transition-all disabled:opacity-50 flex items-center justify-center gap-3 shadow-xl text-white">
                                    {{isScanning ? <Icon name="loader-2" className="animate-spin" /> : <Icon name="sparkles" />}}
                                    {{isScanning ? "아우라 분석 중..." : "청렴 기운 스캔하기"}}
                                </button>
                                {{scanResult && !isScanning && (
                                    <div className="mt-12 animate-scale-in">
                                        <div className="p-1 bg-gradient-to-br from-red-600 via-orange-500 to-yellow-500 rounded-[2.5rem]">
                                            <div className="bg-slate-950 p-8 md:p-10 rounded-[2.4rem]">
                                                <h4 className="text-red-500 font-black text-sm uppercase tracking-widest mb-4">Scan Completed</h4>
                                                <p className="text-2xl md:text-3xl font-black mb-6 leading-tight">"{{scanResult.slogan}}"</p>
                                                <div className="w-12 h-1 bg-slate-800 mx-auto mb-6"></div>
                                                <p className="text-slate-400 text-lg md:text-xl font-medium italic leading-relaxed">{{scanResult.fortune}}</p>
                                            </div>
                                        </div>
                                    </div>
                                )}}
                            </div>
                        </div>
                    </section>

                    {{/* Campaign Section */}}
                    <section id="campaign" className="py-32 px-6 bg-slate-900/50">
                        <div className="max-w-6xl mx-auto">
                            <div className="text-center mb-20">
                                <h2 className="text-red-600 font-black text-sm uppercase tracking-[0.4em] mb-4">Clean Festival Policy</h2>
                                <h3 className="text-4xl md:text-6xl font-black tracking-tighter">설 명절 클린 캠페인 아젠다</h3>
                            </div>
                            <div className="grid md:grid-cols-3 gap-8">
                                {{[
                                    {{ icon: "gift", title: "선물 안 주고 안 받기", desc: "협력사 및 이해관계자와의 명절 선물 교환은 금지됩니다. 마음만 정중히 받겠습니다.", color: "bg-red-600" }},
                                    {{ icon: "coffee", title: "향응 및 편의 제공 금지", desc: "부적절한 식사 대접이나 골프 등 편의 제공은 원천 차단하여 투명성을 지킵니다.", color: "bg-orange-600" }},
                                    {{ icon: "shield-check", title: "부득이한 경우 자진신고", desc: "택배 등으로 배송된 선물은 반송이 원칙이며, 불가피할 시 클린센터로 즉시 신고합니다.", color: "bg-amber-600" }}
                                ].map((item, idx) => (
                                    <div key={{idx}} className="glass-panel p-10 rounded-[3rem] hover:border-red-600/50 transition-all group animate-float" style={{{{animationDelay: `${{idx * 0.5}}s`}}}}>
                                        <div className={{`w-16 h-16 ${{item.color}} rounded-2xl flex items-center justify-center mb-8 group-hover:scale-110 transition-transform shadow-lg`}}>
                                            <Icon name={{item.icon}} size={{32}} />
                                        </div>
                                        <h4 className="text-2xl font-bold mb-4">{{item.title}}</h4>
                                        <p className="text-slate-400 leading-relaxed font-medium">{{item.desc}}</p>
                                    </div>
                                ))}}
                            </div>
                        </div>
                    </section>

                    {{/* Pledge Section */}}
                    <section className="py-32 px-6 bg-red-600/5 relative">
                        <div className="max-w-4xl mx-auto text-center">
                            {{!isPledged ? (
                                <div className="animate-scale-in">
                                    <h2 className="text-5xl md:text-7xl font-black mb-10 tracking-tighter leading-none italic">스스로 다짐하는 <br/> <span className="text-red-600 underline">청렴 서약</span></h2>
                                    <div className="glass-panel p-10 md:p-14 rounded-[4rem] mb-12 shadow-2xl relative overflow-hidden">
                                        <Icon name="award" size={{80}} className="mx-auto mb-8 text-red-600 animate-bounce" />
                                        <h3 className="text-2xl md:text-3xl font-black mb-6">🎁 청렴 실천 응원 이벤트</h3>
                                        <p className="text-lg md:text-xl text-slate-300 font-bold mb-10 leading-relaxed">
                                            참여 인원 <span className="text-red-500">500명 이상</span> 달성 시,<br/>
                                            추첨을 통해 <span className="text-red-500">50분</span>께 커피 쿠폰을 드립니다.
                                        </p>
                                        <form onSubmit={{handlePledgeSubmit}} className="flex flex-col sm:flex-row gap-4">
                                            <input type="text" value={{empId}} onChange={{e => setEmpId(e.target.value)}} placeholder="사번" className="flex-1 px-8 py-5 bg-slate-900 border border-white/10 rounded-3xl outline-none focus:ring-2 focus:ring-red-600 font-bold text-center text-white" required />
                                            <input type="text" value={{empName}} onChange={{e => setEmpName(e.target.value)}} placeholder="성함" className="sm:w-32 px-8 py-5 bg-slate-900 border border-white/10 rounded-3xl outline-none focus:ring-2 focus:ring-red-600 font-bold text-center text-white" required />
                                            <button type="submit" className="px-10 py-5 bg-red-600 text-white font-black rounded-3xl hover:bg-red-500 transition-all shadow-xl">서약하기</button>
                                        </form>
                                    </div>
                                    <p className="text-slate-500 font-black tracking-widest uppercase">Current: {{pledges.length}} Signatures</p>
                                </div>
                            ) : (
                                <div className="animate-scale-in">
                                    <div className="glass-panel p-12 md:p-20 rounded-[4rem] border-b-[12px] border-red-600 shadow-2xl">
                                        <div className="w-24 h-24 bg-green-500 text-white rounded-full flex items-center justify-center mx-auto mb-10 shadow-lg"><Icon name="check" size={{48}} /></div>
                                        <h3 className="text-4xl md:text-6xl font-black mb-6 tracking-tighter italic">서약 완료!</h3>
                                        <p className="text-slate-400 text-xl font-bold mb-16">{{empName}}님, 감사합니다.</p>
                                        
                                        <div className="relative py-16 px-6 bg-slate-900/50 rounded-[3rem] border border-white/5">
                                            <p className="text-xs font-black text-slate-500 mb-8 tracking-[0.6em] uppercase">Participation Rate</p>
                                            <div className="flex items-baseline justify-center gap-4 mb-6">
                                                <span className="text-8xl md:text-[10rem] font-black counter-glitch leading-none text-red-600">{{displayRate}}</span>
                                                <span className="text-4xl font-black text-slate-600">%</span>
                                            </div>
                                            <div className="max-w-md mx-auto h-4 bg-slate-900 rounded-full overflow-hidden mb-6 p-1">
                                                <div className="h-full bg-gradient-to-r from-red-600 to-orange-500 transition-all duration-1000 rounded-full shadow-[0_0_20px_rgba(220,38,38,0.5)]" style={{{{ width: `${{displayRate}}%` }}}}></div>
                                            </div>
                                            <p className="text-slate-400 font-bold">현재 {{pledges.length}}명 참여 (목표: 500명)</p>
                                        </div>
                                    </div>
                                    <button onClick={{() => setIsPledged(false)}} className="mt-12 text-slate-500 hover:text-white transition-all font-bold border-b border-slate-800 pb-1">정보 수정하기</button>
                                </div>
                            )}}
                        </div>
                    </section>
                    
                    <footer className="py-20 text-center border-t border-white/5 text-slate-600">
                        <p className="text-xs font-bold tracking-widest uppercase mb-2">Audit & Ethics Department</p>
                        <p className="text-[10px]">© 2026 ktMOS NORTH.</p>
                    </footer>
                </div>
            );
        }};

        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<App />);
    </script>
</body>
</html>
"""

# 3. Streamlit 화면에 HTML 렌더링 (높이 넉넉하게 설정)
components.html(html_code, height=5000, scrolling=False)
