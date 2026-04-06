import { useEffect, useRef, useState } from "react";
import { Button } from "./Button";
import { colors, radius, spacing, shadow, font } from "../tokens";

interface CameraCaptureProps {
  onCapture: (blob: Blob) => void;
  onClose: () => void;
}

async function getCamera(): Promise<MediaStream> {
  // Try rear camera first (mobile), then any camera (desktop/Mac)
  try {
    return await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
  } catch {
    return await navigator.mediaDevices.getUserMedia({ video: true });
  }
}

export function CameraCapture({ onCapture, onClose }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [blobRef, setBlobRef] = useState<Blob | null>(null);

  const startCamera = async () => {
    setError("");
    setReady(false);
    try {
      const stream = await getCamera();
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => setReady(true);
        videoRef.current.play();
      }
    } catch {
      setError("Could not access camera. Check browser permissions and System Settings > Privacy > Camera.");
    }
  };

  useEffect(() => {
    startCamera();
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const capture = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob) return;
      setBlobRef(blob);
      setPreview(URL.createObjectURL(blob));
      streamRef.current?.getTracks().forEach((t) => t.stop());
    }, "image/jpeg", 0.85);
  };

  const confirm = () => {
    if (blobRef) onCapture(blobRef);
  };

  const retake = () => {
    setPreview(null);
    setBlobRef(null);
    startCamera();
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 10000, fontFamily: font.body, padding: spacing.lg,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: colors.surface, borderRadius: radius.md, padding: spacing.lg,
        maxWidth: 480, width: "100%", boxShadow: shadow.lg,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
          <h3 style={{ margin: 0, fontSize: "16px" }}>Take Photo</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>&#10005;</Button>
        </div>

        {error ? (
          <p style={{ color: colors.danger, fontSize: "14px" }}>{error}</p>
        ) : preview ? (
          <>
            <img src={preview} alt="Preview" style={{ width: "100%", borderRadius: radius.sm, marginBottom: spacing.md }} />
            <div style={{ display: "flex", gap: spacing.sm }}>
              <Button variant="secondary" fullWidth onClick={retake}>Retake</Button>
              <Button variant="primary" fullWidth onClick={confirm}>Use Photo</Button>
            </div>
          </>
        ) : (
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{ width: "100%", minHeight: 250, borderRadius: radius.sm, marginBottom: spacing.md, background: "#000" }}
            />
            {!ready && (
              <p style={{ color: colors.textSecondary, fontSize: "13px", textAlign: "center" }}>Starting camera...</p>
            )}
            <Button variant="primary" fullWidth onClick={capture} disabled={!ready}>Capture</Button>
          </>
        )}
        <canvas ref={canvasRef} style={{ display: "none" }} />
      </div>
    </div>
  );
}
