"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Render content_md của artifact/brief. Tailwind không có @tailwindcss/typography ở
// repo này → style từng thẻ thủ công cho khớp design Clay (ink/feature colors).
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="space-y-2 text-body-sm text-ink/80">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h1 className="text-title-md text-ink" {...p} />,
          h2: (p) => <h2 className="mt-3 text-title-sm text-ink" {...p} />,
          h3: (p) => <h3 className="mt-2 text-body-sm font-semibold text-ink/90" {...p} />,
          p: (p) => <p className="text-ink/80" {...p} />,
          ul: (p) => <ul className="list-disc space-y-1 pl-5" {...p} />,
          ol: (p) => <ol className="list-decimal space-y-1 pl-5" {...p} />,
          li: (p) => <li className="text-ink/80" {...p} />,
          strong: (p) => <strong className="font-semibold text-ink" {...p} />,
          a: (p) => <a className="text-feature-blue underline" target="_blank" rel="noreferrer" {...p} />,
          code: (p) => <code className="rounded bg-ink/5 px-1 py-0.5 text-caption" {...p} />,
          blockquote: (p) => (
            <blockquote className="border-l-2 border-ink/15 pl-3 text-ink/60 italic" {...p} />
          ),
          hr: () => <hr className="my-3 border-ink/10" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
