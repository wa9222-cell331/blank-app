import React from "react";
import { AbsoluteFill, interpolate, useFrame } from "remotion";

const RED_BG = "#DC143C";

interface SectionProps {
  title: string;
  items: string[];
  startFrame: number;
  duration: number;
}

export const Section: React.FC<SectionProps> = ({
  title,
  items,
  startFrame,
  duration,
}) => {
  const endFrame = startFrame + duration;
  const [titleY, setTitleY] = React.useState(-100);
  const [titleOpacity, setTitleOpacity] = React.useState(0);
  const [itemOpacities, setItemOpacities] = React.useState([0, 0, 0, 0]);
  const [containerOpacity, setContainerOpacity] = React.useState(1);

  useFrame((frame) => {
    // 섹션이 시작되기 전이거나 끝난 후
    if (frame < startFrame || frame > endFrame) {
      if (frame > endFrame) {
        setContainerOpacity(0);
      }
      return;
    }

    setContainerOpacity(1);

    // 상대 프레임 (0 = startFrame)
    const relFrame = frame - startFrame;

    // 제목 애니메이션 (0-150프레임)
    if (relFrame < 150) {
      setTitleY(interpolate(relFrame, [0, 150], [-100, 0]));
      setTitleOpacity(interpolate(relFrame, [0, 100], [0, 1]));
    } else {
      setTitleY(0);
      setTitleOpacity(1);
    }

    // 아이템 애니메이션 (150-300, 300-450, ... 형태로 각각 100프레임에 걸쳐 등장)
    const newOpacities = items.map((_, idx) => {
      const itemStartFrame = 150 + idx * 120;
      const itemEndFrame = itemStartFrame + 150;

      if (relFrame < itemStartFrame) return 0;
      if (relFrame > itemEndFrame) return 1;

      return interpolate(relFrame, [itemStartFrame, itemEndFrame], [0, 1]);
    });

    setItemOpacities(newOpacities);
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
        opacity: containerOpacity,
      }}
    >
      {/* 제목 */}
      <div
        style={{
          fontSize: 80,
          fontWeight: 900,
          color: "white",
          marginBottom: 80,
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          textAlign: "center",
        }}
      >
        {title}
      </div>

      {/* 아이템 리스트 */}
      <div
        style={{
          width: "90%",
          maxWidth: 1200,
        }}
      >
        {items.map((item, idx) => (
          <div
            key={idx}
            style={{
              fontSize: 48,
              fontWeight: 500,
              color: "white",
              marginBottom: 50,
              paddingLeft: 60,
              position: "relative",
              opacity: itemOpacities[idx],
            }}
          >
            {/* 불렛 포인트 */}
            <div
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                width: 30,
                height: 30,
                backgroundColor: "white",
                borderRadius: "50%",
              }}
            />
            <div style={{ marginLeft: 20 }}>{item}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
