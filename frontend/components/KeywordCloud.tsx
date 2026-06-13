"use client";

import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { CATEGORICAL_PALETTE } from "@/lib/severity";
import type { KeywordItem } from "@/lib/types";

const VIETNAMESE_FONT_FAMILY =
  'Inter, "Noto Sans", "Noto Sans Vietnamese", "Helvetica Neue", Arial, sans-serif';

const WORD_CLOUD_COLORS = [
  "#5fb0e5",
  "#30323d",
  "#5f7bea",
  "#55d66f",
  "#f4845f",
  "#e84d7a",
  "#37b6b0",
  "#e2c72f",
];

function normalizeKeywordLabel(label: string) {
  return label.normalize("NFC").replace(/\s+/g, " ").trim();
}

export default function KeywordCloud() {
  const { setDim } = useFilters();
  const { data, loading, error } = useStats<KeywordItem[]>(
    "/api/stats/keywords",
    { limit: 50 },
  );

  return (
    <Card title="Từ khóa nổi bật">
      <StatefulChart
        loading={loading}
        error={error}
        data={data}
        isEmpty={(d) => d.length === 0}
      >
        {(d) => {
          const keywords = d
            .map((item) => ({
              ...item,
              label: normalizeKeywordLabel(item.label),
            }))
            .filter((item) => item.label.length > 0);
          const total = keywords.reduce((sum, item) => sum + item.weight, 0);
          const max = Math.max(...keywords.map((x) => x.weight), 1);
          const min = Math.min(...keywords.map((x) => x.weight), max);
          const option = {
            backgroundColor: "transparent",
            title: {
              text: `Top ${keywords.length} từ khóa trên tổng ${total.toLocaleString("vi-VN")} thảo luận`,
              left: 0,
              top: 0,
              textStyle: {
                color: "#232631",
                fontFamily: VIETNAMESE_FONT_FAMILY,
                fontSize: 15,
                fontWeight: 700,
                rich: {
                  number: {
                    color: "#169bd5",
                    fontSize: 20,
                    fontWeight: 800,
                  },
                },
              },
            },
            tooltip: {
              borderWidth: 0,
              backgroundColor: "rgba(35, 38, 49, 0.92)",
              textStyle: {
                color: "#fff",
                fontFamily: VIETNAMESE_FONT_FAMILY,
              },
              formatter: (p: any) => `${p.name}<br/>Tần suất: ${p.value}`,
            },
            series: [
              {
                type: "wordCloud",
                shape: "cardioid",
                left: "center",
                top: 34,
                width: "98%",
                height: "86%",
                sizeRange: [13, 54],
                rotationRange: [0, 0],
                rotationStep: 0,
                gridSize: 10,
                layoutAnimation: false,
                drawOutOfBound: false,
                shrinkToFit: true,
                textStyle: {
                  fontFamily: VIETNAMESE_FONT_FAMILY,
                  fontWeight: 800,
                  lineHeight: 1.12,
                },
                emphasis: {
                  focus: "self",
                  textStyle: {
                    fontFamily: VIETNAMESE_FONT_FAMILY,
                    fontWeight: 900,
                    shadowBlur: 10,
                    shadowColor: "rgba(0,0,0,0.2)",
                  },
                },
                data: keywords.map((x, i) => {
                  const rankBoost = i < 3 ? 1.12 : i < 8 ? 1.04 : 1;
                  const ratio =
                    max === min ? 1 : (x.weight - min) / (max - min);
                  return {
                    name: x.label,
                    value: x.weight,
                    keyword_group_id: x.keyword_group_id,
                    mode: x.mode,
                    textStyle: {
                      fontFamily: VIETNAMESE_FONT_FAMILY,
                      fontSize: Math.round((16 + ratio * 38) * rankBoost),
                      // màu cố định theo thứ hạng → không nhấp nháy mỗi render
                      color:
                        WORD_CLOUD_COLORS[i % WORD_CLOUD_COLORS.length] ??
                        CATEGORICAL_PALETTE[i % CATEGORICAL_PALETTE.length],
                    },
                  };
                }),
              },
            ],
          };
          const onClick = (p: any) => {
            const item = keywords.find((x) => x.label === p.name);
            if (item?.keyword_group_id)
              setDim("keywordGroupId", item.keyword_group_id);
          };
          return (
            <EChart
              option={option}
              height={340}
              onEvents={{ click: onClick }}
            />
          );
        }}
      </StatefulChart>
    </Card>
  );
}
