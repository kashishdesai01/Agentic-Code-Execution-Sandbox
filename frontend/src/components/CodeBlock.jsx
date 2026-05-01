import { useEffect, useRef } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/themes/prism-tomorrow.css";

export default function CodeBlock({ code }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) Prism.highlightElement(ref.current);
  }, [code]);

  return (
    <div className="code-block">
      <pre>
        <code ref={ref} className="language-python">
          {code}
        </code>
      </pre>
    </div>
  );
}
