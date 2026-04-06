import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { Button } from "./Button";
import { colors, radius, spacing } from "../tokens";

interface BarcodeScannerProps {
  onDetected: (barcode: string) => void;
  onClose: () => void;
}

export function BarcodeScanner({ onDetected, onClose }: BarcodeScannerProps) {
  const [error, setError] = useState("");
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const onDetectedRef = useRef(onDetected);
  onDetectedRef.current = onDetected;
  const containerId = "barcode-scanner-container";

  useEffect(() => {
    const scanner = new Html5Qrcode(containerId);
    scannerRef.current = scanner;
    let stopped = false;

    const onSuccess = (decodedText: string) => {
      if (stopped) return;
      stopped = true;
      scanner.stop().catch(() => {});
      onDetectedRef.current(decodedText);
    };
    const config = { fps: 10, qrbox: { width: 250, height: 150 } };

    // Enumerate cameras first (works reliably on Mac/desktop),
    // fall back to facingMode constraints if enumeration fails
    Html5Qrcode.getCameras()
      .then((cameras) => {
        if (stopped) return;
        if (cameras.length === 0) {
          setError("No camera found on this device.");
          return;
        }
        // Prefer back camera on mobile, otherwise use first available
        const backCamera = cameras.find((c) => /back|rear|environment/i.test(c.label));
        const cameraId = backCamera?.id ?? cameras[0].id;
        return scanner.start(cameraId, config, onSuccess, () => {});
      })
      .catch(() => {
        // Fallback: try facingMode constraints
        if (stopped) return;
        return scanner
          .start({ facingMode: "environment" }, config, onSuccess, () => {})
          .catch(() => scanner.start({ facingMode: "user" }, config, onSuccess, () => {}));
      })
      .catch((err) => {
        if (!stopped) {
          setError("Could not access camera. Please allow camera permissions.");
          console.error(err);
        }
      });

    return () => {
      stopped = true;
      scanner.stop().catch(() => {});
    };
  }, []);

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0,0,0,0.8)", zIndex: 1000,
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: spacing.lg,
    }}>
      <div style={{
        background: colors.surface, borderRadius: radius.md, padding: spacing.lg,
        maxWidth: 400, width: "100%",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
          <h3 style={{ margin: 0, fontSize: "16px" }}>Scan Barcode</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>&#10005;</Button>
        </div>
        <div
          id={containerId}
          style={{ width: "100%", minHeight: 200, borderRadius: radius.sm, overflow: "hidden" }}
        />
        {error && (
          <p style={{ color: colors.danger, fontSize: "14px", marginTop: spacing.sm }}>{error}</p>
        )}
        <p style={{ color: colors.textSecondary, fontSize: "13px", marginTop: spacing.sm, textAlign: "center" }}>
          Point your camera at a barcode
        </p>
      </div>
    </div>
  );
}
