import React from "react";
import { AbsoluteFill, interpolate, useFrame } from "remotion";

const RED_BG = "#DC143C";

export const Opening: React.FC = () => {
  const [mainScale, setMainScale] = React.useState(0);
  const [mainOpacity, setMainOpacity] = React.useState(0);
  const [subtitleOpacity, setSubtitleOpacity] = React.useState(0);

  useFrame((frame) => {
    // 프레임 0-300 (0-10초) 동안만 표시
    if (frame > 300) {
      setMainOpacity(0);
      setSubtitleOpacity(0);
      return;
    }

    // 메인 텍스트 스케일 애니메이션 (0-150프레임)
    if (frame < 150) {
      setMainScale(interpolate(frame, [0, 150], [0.3, 1]));
      setMainOpacity(interpolate(frame, [0, 150], [0, 1]));
    } else {
      setMainScale(1);
      setMainOpacity(1);
    }

    // 서브 텍스트 등장 (150-250프레임)
    if (frame > 150) {
      setSubtitleOpacity(interpolate(frame, [150, 250], [0, 1]));
    }
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
      {/* 메인 제목 */}
      <div
        style={{
          fontSize: 120,
          fontWeight: 900,
          color: "white",
          opacity: mainOpacity,
          transform: `scale(${mainScale})`,
          marginBottom: 40,
        }}
      >
        입시 정보
      </div>

      {/* 서브 제목 */}
      <div
        style={{
          fontSize: 48,
          fontWeight: 300,
          color: "white",
          opacity: subtitleOpacity,
          letterSpacing: 2,
        }}
      >
        합격을 위한 전략 가이드
      </div>
    </AbsoluteFill>
  );
};
