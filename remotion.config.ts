import { Config } from "remotion";

Config.setCodec("h264");
Config.setPixelFormat("yuv420p");
Config.setFf({
  outputPixelFormat: "yuv420p",
});
