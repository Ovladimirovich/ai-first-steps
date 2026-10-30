import { useCurrentFrame } from "remotion";
import { PixarCard, PixarHL, PixarTitle } from "../components/PixarCard";
import type { SceneProps } from "../scenes";

export const PS1_3: React.FC<SceneProps> = ({ lines, sceneStart }) => {
  const f = useCurrentFrame();
  const d = (i:number)=> Math.round(((lines[i]?.start??0)-sceneStart)*30);
  return (
    <>
      <div style={{position:"absolute", inset:0, background:"linear-gradient(180deg, #FFF6E0 0%, #FFE9B8 100%)"}}/>
      <PixarTitle light>Тренер, а не костыль</PixarTitle>
      {/* сплит */}
      <div style={{position:"absolute", left:90, top:190, width:1740, height:420, display:"flex", gap:24}}>
        <div style={{
          flex:1, background:"#fff", borderRadius:28, padding:22, boxShadow:"0 18px 40px rgba(0,0,0,.14), inset 0 1px 0 #fff",
          border: f>d(0) ? "3px solid #FF6B6B" : "2px solid #eee", opacity: f>d(0)?1:0.92
        }}>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:26, color:"#FF6B6B"}}>❌ Списать</div>
          <div style={{marginTop:14, background:"#FFF0F0", borderRadius:14, height:140, display:"grid", placeItems:"center", fontSize:56}}>😶‍🌫️ ?</div>
          <div style={{marginTop:12, fontSize:18, color:"#5A3A2A"}}>Голова пустая, спросят — не ответишь</div>
        </div>
        <div style={{
          flex:1, background:"#E0FFF4", borderRadius:28, padding:22, boxShadow:"0 18px 40px rgba(0,0,0,.14)",
          border: f>d(0)? "3px solid #2EE6D6":"2px solid #CDEFE8"
        }}>
          <div style={{fontFamily:"Montserrat, Arial", fontWeight:800, fontSize:26, color:"#1AA89C"}}>✅ С ИИ-репетитором</div>
          <div style={{marginTop:14, background:"#fff", borderRadius:14, height:140, display:"grid", placeItems:"center", fontSize:18, color:"#1B2A4A", textAlign:"center", padding:12, fontWeight:700}}>
            «А теперь <span style={{color:"#2EE6D6"}}>ты</span> объясни мне фотосинтез!»
          </div>
          <div style={{marginTop:12, fontSize:18, color:"#1B2A4A", fontWeight:700}}>Квиз → пересказ → <span style={{color:"#2EE6D6"}}>мышца качается</span></div>
        </div>
      </div>
      {f>d(1) && <PixarCard x={90} y={680} w={840} delay={d(1)} bg="#243A66" size={28}>ИИ даёт <PixarHL>черновик</PixarHL> — ты проверяешь и пересказываешь</PixarCard>}
      {f>d(1)+12 && <PixarCard x={960} y={680} w={870} delay={d(1)+12} bg="#1f5e46" size={28}>Тренер кричит <PixarHL>«ещё раз!»</PixarHL>, а не бежит за тебя 💪</PixarCard>}
    </>
  );
};
