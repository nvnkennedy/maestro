import { Camera, Monitor, Play, Square, Video } from 'lucide-react';
import { useState } from 'react';
import { Spinner } from '../components/common/Spinner';
import { MainLayout } from '../components/layout/MainLayout';
import { useApi } from '../hooks/useApi';
import { getCameraSources, liveCameraUrl } from '../services/api';

/**
 * Live MJPEG feed of the local webcam or the desktop. The desktop source shows
 * this machine's screen — open an RDP client window to watch a remote session.
 */
export function LiveFeedPage() {
  const { data: sources, loading } = useApi(getCameraSources, []);
  const [source, setSource] = useState<'webcam' | 'desktop'>('webcam');
  const [camera, setCamera] = useState('');
  const [running, setRunning] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [error, setError] = useState(false);

  const start = () => {
    setError(false);
    setStreamKey((k) => k + 1);
    setRunning(true);
  };
  const stop = () => setRunning(false);

  // Cache-bust on each Start so the browser opens a fresh stream.
  const src = running
    ? `${liveCameraUrl({
        source,
        camera: source === 'webcam' ? camera : '',
        fps: 12,
        width: 960,
      })}&_=${streamKey}`
    : '';

  const tabClass = (active: boolean) =>
    `flex items-center gap-1.5 px-3 py-1.5 font-medium transition-colors ${
      active ? 'bg-primary text-white' : 'bg-surface text-text-secondary hover:bg-surface-2'
    }`;

  return (
    <MainLayout
      title="Live feed"
      subtitle="Watch the local camera or the desktop (e.g. an open RDP window) live"
      icon={<Video size={18} />}
      iconClass="bg-purple-500/15 text-purple-400"
    >
      {loading ? (
        <Spinner label="Checking camera sources…" />
      ) : !sources?.ffmpeg ? (
        <div className="card p-6 text-sm text-text-secondary">
          <b className="text-text-primary">ffmpeg not found.</b> The live feed needs ffmpeg —
          download <code>ffmpeg.exe</code> from{' '}
          <a
            className="text-primary hover:underline"
            href="https://www.gyan.dev/ffmpeg/builds/"
            target="_blank"
            rel="noreferrer"
          >
            gyan.dev
          </a>{' '}
          and drop it in the app's <code>bin/</code> folder, then refresh.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="card flex flex-wrap items-end gap-4 p-4">
            <div>
              <label className="label">Source</label>
              <div className="inline-flex overflow-hidden rounded-lg border border-border text-sm">
                <button className={tabClass(source === 'webcam')} onClick={() => setSource('webcam')}>
                  <Camera size={14} /> Webcam
                </button>
                {sources.desktop && (
                  <button
                    className={tabClass(source === 'desktop')}
                    onClick={() => setSource('desktop')}
                  >
                    <Monitor size={14} /> Desktop / RDP
                  </button>
                )}
              </div>
            </div>

            {source === 'webcam' && sources.cameras.length > 0 && (
              <div>
                <label className="label">Camera</label>
                <select
                  className="input min-w-[200px]"
                  value={camera}
                  onChange={(e) => setCamera(e.target.value)}
                >
                  <option value="">Auto — first camera</option>
                  {sources.cameras.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="ml-auto flex gap-2">
              {!running ? (
                <button className="btn-primary" onClick={start}>
                  <Play size={15} /> Start
                </button>
              ) : (
                <button className="btn-outline" onClick={stop}>
                  <Square size={15} /> Stop
                </button>
              )}
            </div>
          </div>

          <div className="card flex min-h-[340px] items-center justify-center overflow-hidden bg-black/80 p-2">
            {running && src ? (
              error ? (
                <div className="p-6 text-center text-sm text-text-muted">
                  Could not start the feed. Make sure the {source === 'webcam' ? 'camera' : 'desktop'}{' '}
                  isn't already in use, or pick another source.
                </div>
              ) : (
                <img
                  key={streamKey}
                  src={src}
                  alt="Live feed"
                  className="max-h-[72vh] w-auto rounded"
                  onError={() => setError(true)}
                />
              )
            ) : (
              <div className="p-6 text-center text-sm text-text-muted">
                Press <b className="text-text-primary">Start</b> to view the live{' '}
                {source === 'desktop' ? 'desktop' : 'webcam'} feed.
              </div>
            )}
          </div>

          <p className="text-[11px] text-text-muted">
            {source === 'desktop' ? (
              <>
                Desktop captures this machine's screen — open your RDP client and the remote
                session shows here live.
              </>
            ) : (
              <>The feed comes from the camera connected to the machine running Maestro.</>
            )}{' '}
            The stream stops when you press Stop or leave this page.
          </p>
        </div>
      )}
    </MainLayout>
  );
}
