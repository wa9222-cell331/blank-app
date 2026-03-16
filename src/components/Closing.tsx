import React from "react";
import { AbsoluteFill, interpolate, useFrame } from "remotion";

const RED_BG = "#DC143C";

export const Closing: React.FC = () => {
  const startFrame = 6300; // 210초
  const [textOpacity, setTextOpacity] = React.useState(0);
  const [scale, setScale] = React.useState(0.8);

  useFrame((frame) => {
    // 클로징 섹션 (6300-9000)
    if (frame < startFrame) {
      setTextOpacity(0);
      return;
    }

    const relFrame = frame - startFrame;

    // 텍스트 등장
    if (relFrame < 300) {
      setTextOpacity(interpolate(relFrame, [0, 300], [0, 1]));
      setScale(interpolate(relFrame, [0, 300], [0.8, 1]));
    } else {
      setTextOpacity(1);
      setScale(1);
    }

    // 끝부분 페이드아웃은 Root.tsx에서 처리
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: RED_BG,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: '"Noto Sans KR", sans-serif',
      }}
    >
      <div
        style={{
          fontSize: 72,
          fontWeight: 900,
          color: "white",
          marginBottom: 40,
          opacity: textOpacity,
          transform: `scale(${scale})`,
          textAlign: "center",
        }}
      >
        성공의 열쇠는
        <br />
        조기 준비와 전략
      </div>

      <div
        style={{
          fontSize: 48,
          fontWeight: 400,
          color: "white",
          opacity: textOpacity,
          marginTop: 40,
          textAlign: "center",
        }}
      >
        지금부터 시작하세요!
      </div>
    </AbsoluteFill>
  );
};
