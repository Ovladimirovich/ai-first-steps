import { Composition, staticFile } from "remotion";
import { Main } from "./Main";
import timing from "../public/timing.json";

export const Root = () => (
  <Composition
    id="Main"
    component={Main}
    width={1920}
    height={1080}
    fps={timing.fps}
    durationInFrames={Math.ceil((timing.total + 9) * timing.fps)}
    defaultProps={{ subs: true }}
  />
);
