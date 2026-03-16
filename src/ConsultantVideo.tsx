import React from "react";
import { AbsoluteFill, interpolate, useFrame } from "remotion";
import { Opening } from "./components/Opening";
import { Section } from "./components/Section";
import { Closing } from "./components/Closing";

const SECTIONS = [
  {
    title: "입시 일정",
    items: [
      "수능: 11월 둘째 주 목요일",
      "대입 원서 접수: 9월 중순",
      "수시 합격 발표: 12월 중순",
      "정시 합격 발표: 2월 초순",
    ],
    startFrame: 300, // 10초
    duration: 1200, // 40초
  },
  {
    title: "학종 전형 이해",
    items: [
      "학생부 교과성적 35~40%",
      "학생부 비교과 20~25%",
      "면접평가 35~40%",
      "전형 특성에 따라 반영 비율 상이",
    ],
    startFrame: 1500, // 50초
    duration: 1200, // 40초
  },
  {
    title: "지원 전략",
    items: [
      "상향지원 1~2개, 적정지원 2~3개",
      "하향지원 2~3개로 포트폴리오 구성",
      "충원지원 고려하기",
      "학과 특성에 맞는 지원 전략 수립",
    ],
    startFrame: 2700, // 90초
    duration: 1200, // 40초
  },
  {
    title: "입시 준비 팁",
    items: [
      "교사추천서는 충분한 소통 후 의뢰",
      "자소서는 3주 이상 구상하기",
      "면접은 최소 10회 이상 연습",
      "과목별 심화 학습으로 면접 대비",
    ],
    startFrame: 3900, // 130초
    duration: 1200, // 40초
  },
  {
    title: "성공의 핵심",
    items: [
      "일관성 있는 활동 기록",
      "학교생활에 충실한 태도",
      "조기 준비와 전략적 지원",
      "실패를 배움으로 받아들이기",
    ],
    startFrame: 5100, // 170초
    duration: 1200, // 40초
  },
];

export const ConsultantVideo = () => {
  const [frameOpacity, setFrameOpacity] = React.useState(1);

  useFrame((frame) => {
    // 전체 영상이 끝나갈 때 페이드아웃
    if (frame > 8700) {
      setFrameOpacity(1 - (frame - 8700) / 300);
    }
  });

  return (
    <AbsoluteFill style={{ opacity: frameOpacity }}>
      {/* 오프닝 */}
      <Opening />

      {/* 섹션들 */}
      {SECTIONS.map((section, idx) => (
        <Section
          key={idx}
          title={section.title}
          items={section.items}
          startFrame={section.startFrame}
          duration={section.duration}
        />
      ))}

      {/* 클로징 */}
      <Closing />
    </AbsoluteFill>
  );
};
