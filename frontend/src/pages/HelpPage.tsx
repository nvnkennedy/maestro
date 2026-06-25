import { BookOpen } from 'lucide-react';
import { ReactNode } from 'react';
import { MainLayout } from '../components/layout/MainLayout';
import { useApi } from '../hooks/useApi';
import { getHealth } from '../services/api';

function Code({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[12px] text-primary">
      {children}
    </code>
  );
}

function Block({ children }: { children: string }) {
  return (
    <pre className="my-2 overflow-auto rounded-lg border border-border bg-[#0b1220] p-3 font-mono text-[12px] leading-relaxed text-slate-200">
      {children}
    </pre>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="card scroll-mt-4 p-5">
      <h2 className="mb-3 text-lg font-bold text-text-primary">{title}</h2>
      <div className="space-y-3 text-sm leading-relaxed text-text-secondary">{children}</div>
    </section>
  );
}

const TOC = [
  ['about', 'About & install'],
  ['quick-start', 'Quick start'],
  ['scripts', 'Run your own scripts (where to put them)'],
  ['adapt', 'Adapt .py / .bat / .ps1 / .cmd / .exe'],
  ['dlt', 'DLT — match vs logging'],
  ['devices', 'Power / ETFW / Serial / SSH / ADB'],
  ['designer', 'Designer (canvas, branches, attachments)'],
  ['shortcuts', 'Keyboard shortcuts'],
  ['run', 'Run & live logs'],
  ['reports', 'Reports (Allure / Playwright)'],
  ['plugins', 'Custom adapter plugin'],
  ['package', 'Packaging'],
];

export function HelpPage() {
  const { data: health } = useApi(getHealth, []);
  return (
    <MainLayout
      title="Help & Readme"
      subtitle="About, install, and how to use Maestro"
      icon={<BookOpen size={18} />}
      iconClass="bg-cyan-500/15 text-cyan-400"
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[230px_1fr]">
        {/* Table of contents */}
        <div className="card sticky top-0 h-fit p-4">
          <div className="section-title mb-2">On this page</div>
          <nav className="space-y-1 text-sm">
            {TOC.map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="block rounded-md px-2 py-1 text-text-secondary hover:bg-surface-2 hover:text-text-primary"
              >
                {label}
              </a>
            ))}
          </nav>
        </div>

        <div className="space-y-4">
          <Section id="about" title="About Maestro">
            <div className="flex flex-wrap items-center gap-3">
              <span className="badge bg-primary/15 text-primary">
                Version {health?.version ?? '…'}
              </span>
              <span className="badge bg-emerald-500/15 text-emerald-400">
                {health?.status === 'ok' ? 'Backend online' : 'Backend …'}
              </span>
              <span className="badge bg-teal-500/15 text-teal-300">
                Created by Naveen Daniel Kennedy
              </span>
            </div>
            <p>
              Maestro is an automotive test-automation framework: design tests by
              drag-and-drop, run them locally or on a remote <b>RDP machine</b>, and
              get Allure-style HTML reports — including a single aggregated report per
              suite/scenario run.
            </p>
            <p className="font-semibold text-text-primary">Architecture (at a glance)</p>
            <ul className="list-disc space-y-1 pl-5">
              <li><b>Backend</b>: FastAPI + SQLAlchemy (SQLite), WebSocket live logs, APScheduler.</li>
              <li><b>Adapters</b> (manifest plugins): SSH, ADB, system/scripts, camera, serial.</li>
              <li><b>Run Targets</b>: Local or a remote/RDP machine reached over SSH (DOMAIN\\user).</li>
              <li><b>Frontend</b>: React + Vite, served by the backend in production.</li>
              <li><b>Security</b>: AES-256-GCM credential vault, role-based access, audit log.</li>
            </ul>
            <p className="font-semibold text-text-primary">How to install</p>
            <ul className="list-disc space-y-1 pl-5">
              <li><b>PyPI (recommended)</b> — <Code>pip install maestro-automation</Code>, then run <Code>maestro</Code>. Pulls turboadb + turbossh automatically.</li>
              <li><b>Self-contained folder</b> — run <Code>maestro-setup</Code> for a dedicated venv + data folder + a one-click launcher.</li>
              <li><b>Source</b> — <Code>pip install -r requirements.txt</Code> then <Code>python app.py</Code> (builds the UI on first run).</li>
            </ul>
            <p>
              Full details: <Code>docs/INSTALL.md</Code>, <Code>docs/HOWTO.md</Code> and{' '}
              <Code>MAESTRO_COMPLETE_ARCHITECTURE.md</Code> in the project.
            </p>
          </Section>

          <Section id="quick-start" title="Quick start">
            <ol className="list-decimal space-y-1.5 pl-5">
              <li><b>Configuration</b> — add a <b>Target</b> for any device you talk to (SSH host, ADB device, serial port, camera). Credentials are encrypted.</li>
              <li><b>Test Designer</b> — pick/create a test case, drag actions from the palette onto the canvas, wire them up.</li>
              <li><b>Execution</b> — pick a case/scenario/suite and press <b>Start</b>. Watch live logs and step status.</li>
              <li><b>Reports</b> — open a finished run as an Allure- or Playwright-style report; download or compare.</li>
            </ol>
            <p>Set who you are with the user chip in the top bar — it's recorded as <i>Triggered by</i> on every run.</p>
          </Section>

          <Section id="scripts" title="Run your own scripts (where to put them)">
            <p>
              <b>There is no special folder.</b> Keep your scripts wherever they already
              live (e.g. <Code>C:\bench\</Code>) and reference them by their <b>full path</b>.
              Maestro runs them as-is — you don't change your scripts.
            </p>
            <p>Use the <b>Script</b> group in the palette:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li><Code>system.run_file</Code> — run a script/exe file (interpreter auto-detected from the extension).</li>
              <li><Code>system.run_command</Code> — run any command line through the shell.</li>
            </ul>
            <p>Common parameters on <Code>run_file</Code>:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li><Code>path</Code> — full path to your file.</li>
              <li><Code>args</Code> — a list, e.g. <Code>["on", "--verbose"]</Code>.</li>
              <li><Code>cwd</Code> — working directory (defaults to the script's folder).</li>
              <li><Code>env</Code> — extra environment variables, e.g. <Code>{'{ "TARGET": "ECU1" }'}</Code>.</li>
              <li><Code>timeout</Code> — seconds before it's stopped.</li>
              <li><Code>expect_contains</Code> — text that must appear in stdout → pass/fail.</li>
              <li><Code>attach_output</Code> — attach the full stdout to the report.</li>
            </ul>
            <p>
              <b>Live logs:</b> every line your script prints streams into the Execution
              console as it runs — just <Code>print</Code> / <Code>Write-Host</Code> /
              <Code>echo</Code> progress and you'll see it live.
            </p>
          </Section>

          <Section id="adapt" title="Adapt .py / .bat / .ps1 / .cmd / .exe">
            <p>The interpreter is chosen automatically from the file extension:</p>
            <Block>{`.ps1  -> powershell -NoProfile -ExecutionPolicy Bypass -File <file> <args>
.bat  -> cmd /c <file> <args>
.cmd  -> cmd /c <file> <args>
.py   -> python <file> <args>     (set python_path to override)
.sh   -> bash <file> <args>
.exe  -> <file> <args>            (run directly)`}</Block>
            <p>Examples (set these on a <Code>run_file</Code> step):</p>
            <Block>{`PowerShell:  path = C:\\bench\\power.ps1     args = ["cycle"]
Batch:       path = C:\\bench\\flash.bat     args = ["image.bin"]
Python:      path = C:\\bench\\check.py       args = ["--ecu", "1"]
Exe:         path = C:\\tools\\probe.exe       args = ["--scan"]`}</Block>
            <p>
              For a one-off command line, use <Code>run_command</Code> with
              <Code>command</Code>, e.g. <Code>C:\bench\power.ps1 cycle &amp;&amp; timeout /t 3</Code>.
            </p>
          </Section>

          <Section id="dlt" title="DLT — match vs logging">
            <p>Run your DLT script with <Code>run_file</Code>, then choose a mode:</p>
            <p><b>Match mode</b> — pass only if a pattern is found in the produced trace, and attach it on match:</p>
            <Block>{`path          = C:\\bench\\dlt_capture.py
match_file    = C:\\bench\\out\\run.dlt
match_pattern = BootComplete
match_required = true`}</Block>
            <p><b>Logging mode</b> — just run it and attach the trace, no matching:</p>
            <Block>{`path        = C:\\bench\\dlt_capture.py
attach_file = C:\\bench\\out\\run.dlt`}</Block>
            <p>
              Attached files (matched or logged) show up on that step in the <b>report</b>.
              You can also attach several with <Code>attach_files</Code>.
            </p>
          </Section>

          <Section id="devices" title="Power / ETFW / Serial / SSH / ADB">
            <p>
              <b>Have your own scripts?</b> Run them with <Code>run_file</Code> (above) —
              that's the simplest path for power / ETFW / DLT and works with any arguments.
            </p>
            <p>Or use the built-in adapters via a <b>Target</b> in Configuration:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li><b>SSH</b> — host, username, optional Windows <b>domain</b> (logs in as <Code>DOMAIN\user</Code> for remote/RDP hosts), password. Actions: run command, upload/download, mount, capture journal/slog.</li>
              <li><b>ADB</b> — device serial; shell, install/uninstall, logcat, screenshot, mount/remount.</li>
              <li><b>Serial</b> — COM port + baudrate; wait-for-pattern, send, monitor, list ports.</li>
              <li><b>Camera</b> — <Code>capture_webcam</Code> (single frame), <Code>record_video</Code>, desktop <Code>screenshot</Code>. Needs <b>ffmpeg</b> — drop <Code>ffmpeg.exe</Code> into the app's <Code>bin\</Code> folder.</li>
              <li><b>Power / ETFW</b> — point at your script/tool path (these assume on/off/cycle-style verbs; prefer <Code>run_file</Code> if your scripts differ).</li>
            </ul>
          </Section>

          <Section id="designer" title="Designer (canvas, branches, attachments)">
            <ul className="list-disc space-y-1 pl-5">
              <li><b>Canvas vs List</b> — toggle at the top of the editor. The canvas shows nodes + connectors; the palette appears only while a case is open.</li>
              <li><b>Add</b> — click <Code>+</Code> on a palette action, or "Add node".</li>
              <li><b>Edit</b> — double-click a node. <b>Timeout</b> — click the ⏱ chip on a node to cycle it.</li>
              <li><b>Branches</b> — the <b>Yes/No</b> button makes a node a decision: checks the previous step's output and routes accordingly.</li>
              <li><b>Parallel</b> — group adjacent steps to run together (in the step editor's Execution flow).</li>
              <li><b>Attachments</b> — in the step editor, attach files (e.g. an APK or expected output) that travel with the step and show in the report.</li>
            </ul>
          </Section>

          <Section id="shortcuts" title="Keyboard shortcuts">
            <ul className="list-disc space-y-1 pl-5">
              <li><b>Click</b> a node to select it (highlight).</li>
              <li><b>Delete</b> / Backspace — remove the selected node.</li>
              <li><b>Ctrl/Cmd + C / X / V</b> — copy / cut / paste a node.</li>
              <li><b>Ctrl/Cmd + D</b> — duplicate the selected node.</li>
              <li><b>F2</b> — focus the test-case name. <b>Ctrl + S</b> — save.</li>
            </ul>
            <p>Leaving the designer with unsaved changes prompts before discarding.</p>
          </Section>

          <Section id="run" title="Run & live logs">
            <ul className="list-disc space-y-1 pl-5">
              <li>Pick scope <b>case / scenario / suite</b>, then <b>Start</b> (or "Run later" to schedule).</li>
              <li>Live logs stream in real time; the running step shows a ticking timer; search the log box.</li>
              <li>Step-by-step mode pauses before each step until you press <b>Next</b>.</li>
              <li>When a run finishes, the <Code>RUN-N ↗</Code> id and "View report" jump to its report.</li>
            </ul>
          </Section>

          <Section id="reports" title="Reports (Allure / Playwright)">
            <p>
              Open a run, choose the <b>report format</b> (Allure-style or Playwright-style),
              then Open or Download. Reports embed step output, errors, attachments and the
              environment. You can compare two runs and bulk-delete.
            </p>
          </Section>

          <Section id="plugins" title="Custom adapter plugin (reusable)">
            <p>
              To turn a script into a reusable action available everywhere, add a folder under
              <Code>data\plugins\&lt;name&gt;\</Code> with a <Code>manifest.json</Code> and an
              <Code>adapter.py</Code> subclassing <Code>BaseAdapter</Code>:
            </p>
            <Block>{`manifest.json
{ "name": "myscript", "version": "1.0", "entry_point": "adapter:MyScriptAdapter" }

adapter.py
from backend.adapters.base_adapter import AdapterResult, BaseAdapter
class MyScriptAdapter(BaseAdapter):
    name = "myscript"
    def _register_actions(self):
        self.actions = {"do_thing": self._do_thing}
    async def _do_thing(self, params):
        return await self._run_subprocess(["python", r"C:\\x.py"], timeout=60)`}</Block>
            <p>Then restart, or use <b>Plugins → Reload</b>. Your actions appear as <Code>myscript.do_thing</Code>.</p>
          </Section>

          <Section id="package" title="Packaging">
            <p>
              Maestro ships as a single <b>PyPI wheel</b> (backend + bundled UI, no
              binaries). Build it with <Code>python scripts/build_pypi.py</Code> and publish
              with <Code>python -m twine upload dist/*</Code>. See <Code>PACKAGING.md</Code> for
              details, including how your scripts and ffmpeg are provisioned at runtime.
            </p>
          </Section>
        </div>
      </div>
    </MainLayout>
  );
}
