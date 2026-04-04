import { useRef, useState } from "react";
import Tesseract from "tesseract.js";
import { Button } from "./Button";
import { Spinner } from "./Spinner";
import { colors, radius, spacing, baseStyles } from "../tokens";

interface OCRScannerProps {
  onDetected: (text: string) => void;
  onClose: () => void;
  label?: string;
}

export function OCRScanner({ onDetected, onClose, label = "Scan Text" }: OCRScannerProps) {
  const [processing, setProcessing] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [results, setResults] = useState<string[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraActive, setCameraActive] = useState(false);

  const startCamera = async () => {
    try {
      // Try rear camera first (mobile), fall back to any camera (desktop/Mac)
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
      }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setCameraActive(true);
    } catch {
      // Camera not available, fall back to file input
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraActive(false);
  };

  const captureAndOCR = async () => {
    let imageSource: string;

    if (cameraActive && videoRef.current) {
      // Capture frame from video
      const canvas = document.createElement("canvas");
      canvas.width = videoRef.current.videoWidth;
      canvas.height = videoRef.current.videoHeight;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(videoRef.current, 0, 0);
      imageSource = canvas.toDataURL("image/png");
      setPreview(imageSource);
      stopCamera();
    } else {
      return;
    }

    setProcessing(true);
    try {
      const result = await Tesseract.recognize(imageSource, "eng", {});
      const lines = result.data.text
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l.length > 2);
      setResults(lines);
    } catch (err) {
      console.error("OCR failed:", err);
    } finally {
      setProcessing(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    setProcessing(true);
    try {
      const result = await Tesseract.recognize(url, "eng", {});
      const lines = result.data.text
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l.length > 2);
      setResults(lines);
    } catch (err) {
      console.error("OCR failed:", err);
    } finally {
      setProcessing(false);
    }
  };

  const handleClose = () => {
    stopCamera();
    onClose();
  };

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0,0,0,0.8)", zIndex: 1000,
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: spacing.lg,
    }}>
      <div style={{
        background: colors.surface, borderRadius: radius.md, padding: spacing.lg,
        maxWidth: 420, width: "100%", maxHeight: "90vh", overflowY: "auto",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
          <h3 style={{ margin: 0, fontSize: "16px" }}>{label}</h3>
          <Button variant="ghost" size="sm" onClick={handleClose}>✕</Button>
        </div>

        {!cameraActive && !preview && (
          <div style={{ display: "flex", flexDirection: "column", gap: spacing.sm }}>
            <Button variant="primary" onClick={startCamera} fullWidth>Open Camera</Button>
            <div style={{ textAlign: "center", color: colors.textSecondary, fontSize: "13px" }}>or</div>
            <label style={{ display: "block" }}>
              <input type="file" accept="image/*" capture="environment" onChange={handleFileUpload}
                style={{ display: "none" }} />
              <Button variant="secondary" fullWidth onClick={() => {}} style={{ pointerEvents: "none" }}>
                Upload Photo
              </Button>
            </label>
          </div>
        )}

        {cameraActive && (
          <div>
            <video ref={videoRef} style={{ width: "100%", borderRadius: radius.sm }} autoPlay playsInline muted />
            <Button variant="primary" fullWidth onClick={captureAndOCR} style={{ marginTop: spacing.sm }}>
              Capture & Read Text
            </Button>
          </div>
        )}

        {processing && <Spinner label="Reading text..." />}

        {preview && !processing && results.length > 0 && (
          <div style={{ marginTop: spacing.md }}>
            <img src={preview} style={{ width: "100%", borderRadius: radius.sm, marginBottom: spacing.sm }} alt="Captured" />
            <p style={{ fontSize: "13px", color: colors.textSecondary, marginBottom: spacing.xs }}>Detected text (click to use):</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              {results.map((line, i) => (
                <div
                  key={i}
                  onClick={() => { onDetected(line); handleClose(); }}
                  style={{
                    padding: "8px 12px", background: colors.surfaceMuted,
                    borderRadius: radius.sm, cursor: "pointer", fontSize: "14px",
                    border: `1px solid ${colors.border}`,
                  }}
                >
                  {line}
                </div>
              ))}
            </div>
          </div>
        )}

        {preview && !processing && results.length === 0 && (
          <div style={{ textAlign: "center", padding: spacing.lg, color: colors.textSecondary }}>
            <p>No text detected. Try again with better lighting.</p>
            <Button variant="secondary" onClick={() => { setPreview(null); startCamera(); }}>Retry</Button>
          </div>
        )}
      </div>
    </div>
  );
}
