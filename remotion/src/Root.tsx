import { Composition } from "remotion";
import { Main } from "./Main";
import { PixarMain } from "./PixarMain";
import timing from "../public/timing.json";
import timingPixar from "../public/timing-pixar.json";

export const Root = () => (
  <>
    <Composition
      id="Main"
      component={Main}
      width={1920}
      height={1080}
      fps={timing.fps}
      durationInFrames={Math.ceil((timing.total + 9) * timing.fps)}
      defaultProps={{ subs: true }}
    />
    <Composition
      id="PixarWhyAI"
      component={PixarMain}
      width={1920}
      height={1080}
      fps={timingPixar.fps}
      durationInFrames={Math.ceil((timingPixar.total + 6) * timingPixar.fps)}
      defaultProps={{ subs: true }}
    />
  </>
);
