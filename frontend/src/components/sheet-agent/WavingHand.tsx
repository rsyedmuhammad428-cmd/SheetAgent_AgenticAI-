export function WavingHand({ className = "" }: { className?: string }) {
  return (
    <span
      role="img"
      aria-label="waving hand"
      className={`inline-block origin-[70%_70%] ${className}`}
      style={{ animation: "wave 2.2s ease-in-out infinite" }}
    >
      👋
      <style>{`
        @keyframes wave {
          0%   { transform: rotate(0deg); }
          10%  { transform: rotate(14deg); }
          20%  { transform: rotate(-8deg); }
          30%  { transform: rotate(14deg); }
          40%  { transform: rotate(-4deg); }
          50%  { transform: rotate(10deg); }
          60%  { transform: rotate(0deg); }
          100% { transform: rotate(0deg); }
        }
      `}</style>
    </span>
  );
}
