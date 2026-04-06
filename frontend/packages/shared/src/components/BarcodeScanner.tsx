import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { Button } from "./Button";
import { colors, radius, spacing } from "../tokens";

interface BarcodeScannerProps {
  onDetected: (barcode: string) => void;
  onClose: () => void;
}

let idCounter = 0;

export function BarcodeScanner({ onDetected, onClose }: BarcodeScannerProps) {
  const [error, setError] = useState("");
  const [status, setStatus] = useState("Requesting camera access...");
  const onDetectedRef = useRef(onDetected);
  onDetectedRef.current = onDetected;
  const [containerId] = useState(() => `barcode-scanner-${++idCounter}`);

  useEffect(() => {
    let stopped = false;
    let running = false;
    let scanner: Html5Qrcode | null = null;

    const timer = setTimeout(async () => {
      if (stopped) return;
      const el = document.getElementById(containerId);
      if (!el) {
        setError("Scanner container not found.");
        return;
      }

      try {
        scanner = new Html5Qrcode(containerId);
      } catch {
        setError("Failed to initialize scanner.");
        return;
      }

      const onSuccess = (decodedText: string) => {
        if (stopped) return;
        stopped = true;
        if (running) scanner?.stop().catch(() => {});
        running = false;
        onDetectedRef.current(decodedText);
      };
      const config = { fps: 10, qrbox: { width: 250, height: 150 } };

      try {
        const cameras = await Html5Qrcode.getCameras();
        if (stopped) return;
        if (cameras.length === 0) { setError("No camera found."); return; }
        setStatus(`Found ${cameras.length} camera(s). Starting...`);
        const backCam = cameras.find((c) => /back|rear|environment/i.test(c.label));
        await scanner.start(backCam?.id ?? cameras[0].id, config, onSuccess, () => {});
        running = true;
        if (!stopped) setStatus("");
      } catch {
        if (stopped) return;
        try {
          await scanner.start({ facingMode: "user" }, config, onSuccess, () => {});
          running = true;
          if (!stopped) setStatus("");
        } catch (err: any) {
          if (!stopped) {
            setError(`Camera error: ${err?.message || "Unknown"}. Check browser permissions.`);
            setStatus("");
          }
        }
      }
    }, 150);

    return () => {
      stopped = true;
      clearTimeout(timer);
      if (running && scanner) {
        scanner.stop().catch(() => {});
        running = false;
      }
    };
  }, [containerId]);

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
          style={{ width: "100%", minHeight: 250, borderRadius: radius.sm, overflow: "hidden", background: "#000" }}
        />
        {status && (
          <p style={{ color: colors.textSecondary, fontSize: "13px", marginTop: spacing.sm, textAlign: "center" }}>{status}</p>
        )}
        {error && (
          <p style={{ color: colors.danger, fontSize: "14px", marginTop: spacing.sm }}>{error}</p>
        )}
        {!status && !error && (
          <p style={{ color: colors.textSecondary, fontSize: "13px", marginTop: spacing.sm, textAlign: "center" }}>
            Point your camera at a barcode
          </p>
        )}
      </div>
    </div>
  );
}
