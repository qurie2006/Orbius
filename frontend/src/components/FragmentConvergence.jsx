export default function FragmentConvergence() {
  return (
    <div className="convergence-illustration">
      <svg
        className="convergence-illustration__svg"
        viewBox="0 0 640 440"
        role="img"
        aria-labelledby="convergence-title convergence-description"
      >
        <title id="convergence-title">From source fragments to traceable requirements</title>
        <desc id="convergence-description">
          A conceptual illustration of document, conversation, and image inputs connecting to an organized requirement and its evidence.
        </desc>

        <path className="convergence-illustration__route route-one" d="M150 107 C225 107 225 205 302 205" />
        <path className="convergence-illustration__route route-two" d="M150 220 C218 220 235 220 302 220" />
        <path className="convergence-illustration__route route-three" d="M150 333 C225 333 225 235 302 235" />
        <path className="convergence-illustration__route route-output" d="M350 220 C390 220 394 220 428 220" />

        <g className="convergence-illustration__source source-document">
          <rect x="28" y="75" width="126" height="64" rx="8" />
          <path d="M44 94h18m-18 8h48m-48 8h38" />
          <text x="101" y="113">DOCUMENT</text>
        </g>
        <g className="convergence-illustration__source source-audio">
          <rect x="28" y="188" width="126" height="64" rx="8" />
          <path d="M44 220h4l4-12 6 24 6-18 5 11 5-8 5 3h7" />
          <text x="101" y="224">VOICE</text>
        </g>
        <g className="convergence-illustration__source source-image">
          <rect x="28" y="301" width="126" height="64" rx="8" />
          <rect x="44" y="317" width="31" height="27" rx="3" />
          <circle cx="66" cy="325" r="3" />
          <path d="m47 340 8-9 5 5 4-4 8 8" />
          <text x="101" y="337">IMAGE</text>
        </g>

        <g className="convergence-illustration__core">
          <circle cx="326" cy="220" r="32" />
          <circle cx="326" cy="220" r="22" />
          <path d="M316 220h20m-10-10v20" />
          <text x="326" y="276">SYNTHESIS</text>
        </g>

        <g className="convergence-illustration__output">
          <rect x="428" y="153" width="184" height="50" rx="7" />
          <circle cx="445" cy="178" r="4" />
          <path d="M459 172h88m-88 11h128" />
          <text x="459" y="165">REQUIREMENT</text>

          <rect x="428" y="218" width="184" height="50" rx="7" />
          <path d="M442 236h7v7h-7zm11 0h7v7h-7zm-11 11h7v7h-7z" />
          <path d="M471 238h99m-99 10h76" />
          <text x="471" y="231">EVIDENCE LINK</text>

          <rect x="428" y="283" width="184" height="50" rx="7" />
          <path d="M443 308h7l5-8 7 16 5-8h8" />
          <path d="M484 302h88m-88 11h61" />
          <text x="484" y="296">DECISION</text>
        </g>

        <text className="convergence-illustration__label" x="28" y="42">FRAGMENTED INPUTS</text>
        <text className="convergence-illustration__label" x="428" y="375">STRUCTURED · TRACEABLE · REVIEWABLE</text>
        <path className="convergence-illustration__rule" d="M28 397H612" />
      </svg>
      <p className="convergence-illustration__caption">
        A conceptual view of the Orbius method — not a live processing trace.
      </p>
    </div>
  );
}
