import { Composition } from "remotion";
import { ConsultantVideo } from "./ConsultantVideo";

export const Root = () => {
  return (
    <Composition
      id="ConsultantVideo"
      component={ConsultantVideo}
      durationInFrames={9000}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{}}
    />
  );
};
