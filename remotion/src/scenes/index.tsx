import type { Line } from "../Main";
import { S0_1 } from "./S0_1";
import { S1_1 } from "./S1_1";
import { S1_2 } from "./S1_2";
import { S1_3 } from "./S1_3";
import { S1_4 } from "./S1_4";
import { S2_1 } from "./S2_1";
import { S2_2 } from "./S2_2";
import { S2_3 } from "./S2_3";
import { S2_4 } from "./S2_4";
import { S2_5 } from "./S2_5";
import { S3_1 } from "./S3_1";
import { S4_1, S4_2, S4_3, S4_4 } from "./S4_x";
import { S4_5 } from "./S4_5";
import { S5_1, S5_2, S5_3 } from "./S5_x";
import { S5_4, S6_1, S6_2, S6_3 } from "./S6_x";
import { S7_1, S7_2, S8_1 } from "./S7_x";
import { S0_2 } from "./S0_2";
import { S8_2 } from "./S8_2";
import { Placeholder } from "./Placeholder";

export type SceneProps = { sceneId: string; lines: Line[]; sceneStart: number };
export const SCENES: Record<string, React.FC<SceneProps>> = {
  "0.1": S0_1, "0.2": S0_2, "1.1": S1_1, "1.2": S1_2, "1.3": S1_3, "1.4": S1_4, "2.1": S2_1, "2.2": S2_2, "2.3": S2_3, "2.4": S2_4, "2.5": S2_5, "3.1": S3_1, "4.1": S4_1, "4.2": S4_2, "4.3": S4_3, "4.4": S4_4, "4.5": S4_5, "5.1": S5_1, "5.2": S5_2, "5.3": S5_3, "5.4": S5_4, "6.1": S6_1, "6.2": S6_2, "6.3": S6_3, "7.1": S7_1, "7.2": S7_2, "8.1": S8_1, "8.2": S8_2, _placeholder: Placeholder,
};
