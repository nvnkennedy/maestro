/** Human-friendly catalog of every adapter action, for non-technical users. */

export interface ActionOption {
  value: string;
  label: string;
  group: string;
}

export const ACTION_OPTIONS: ActionOption[] = [
  { value: 'ssh.execute_command', label: 'Run command on target (SSH)', group: 'SSH' },
  { value: 'ssh.upload_file', label: 'Upload file to target (SCP)', group: 'SSH' },
  { value: 'ssh.download_file', label: 'Download file from target (SCP)', group: 'SSH' },
  { value: 'ssh.remount_rw', label: 'Remount filesystem read-write', group: 'SSH' },
  { value: 'ssh.file_exists', label: 'Check a file/path exists', group: 'SSH' },
  { value: 'ssh.list_dir', label: 'List a directory', group: 'SSH' },
  { value: 'ssh.tail_file', label: 'Tail a log file (attach)', group: 'SSH' },
  { value: 'ssh.process_status', label: 'Check process / service running', group: 'SSH' },
  { value: 'ssh.reboot', label: 'Reboot the host', group: 'SSH' },
  { value: 'ssh.capture_journal', label: 'Attach journalctl log', group: 'SSH' },
  { value: 'ssh.capture_slog2info', label: 'Attach slog2info log (QNX)', group: 'SSH' },
  { value: 'adb.list_devices', label: 'List connected Android devices', group: 'ADB' },
  { value: 'adb.shell', label: 'Run ADB shell command', group: 'ADB' },
  { value: 'adb.push', label: 'Push file to device', group: 'ADB' },
  { value: 'adb.pull', label: 'Pull file from device', group: 'ADB' },
  { value: 'adb.install_apk', label: 'Install APK', group: 'ADB' },
  { value: 'adb.uninstall_apk', label: 'Uninstall app package', group: 'ADB' },
  { value: 'adb.logcat_dump', label: 'Attach logcat log', group: 'ADB' },
  { value: 'adb.logcat_clear', label: 'Clear logcat buffer', group: 'ADB' },
  { value: 'adb.screenshot', label: 'Device screenshot', group: 'ADB' },
  { value: 'adb.screenrecord', label: 'Record device screen', group: 'ADB' },
  { value: 'adb.reboot', label: 'Reboot device', group: 'ADB' },
  { value: 'adb.wait_for_device', label: 'Wait until device is online', group: 'ADB' },
  { value: 'power.power_on', label: 'Power ON', group: 'Power' },
  { value: 'power.power_off', label: 'Power OFF', group: 'Power' },
  { value: 'power.power_cycle', label: 'Power cycle', group: 'Power' },
  { value: 'power.enter_edl', label: 'Enter EDL mode', group: 'Power' },
  { value: 'power.status', label: 'Read power status', group: 'Power' },
  { value: 'etfw.bus_sleep_on', label: 'Bus sleep ON (ETFW)', group: 'ETFW' },
  { value: 'etfw.bus_sleep_off', label: 'Bus sleep OFF (ETFW)', group: 'ETFW' },
  { value: 'etfw.set_state', label: 'Set ECU state (ETFW)', group: 'ETFW' },
  { value: 'etfw.get_state', label: 'Read ECU state (ETFW)', group: 'ETFW' },
  { value: 'dlt.start_capture', label: 'Start DLT capture', group: 'DLT' },
  { value: 'dlt.stop_capture', label: 'Stop DLT capture', group: 'DLT' },
  { value: 'dlt.save_file', label: 'Attach DLT file to report', group: 'DLT' },
  { value: 'camera.capture', label: 'Webcam: photo OR video (set mode)', group: 'Camera' },
  { value: 'camera.capture_webcam', label: 'Webcam photo (single frame)', group: 'Camera' },
  { value: 'camera.record_video', label: 'Webcam video (record N seconds)', group: 'Camera' },
  { value: 'camera.screenshot', label: 'Desktop screenshot', group: 'Camera' },
  { value: 'camera.detect', label: 'Detect cameras on this PC', group: 'Camera' },
  { value: 'camera.list_devices', label: 'List capture devices (ffmpeg)', group: 'Camera' },
  { value: 'serial.wait_for_pattern', label: 'Wait for text on serial console', group: 'Serial' },
  { value: 'serial.monitor', label: 'Monitor serial console', group: 'Serial' },
  { value: 'serial.send', label: 'Send to serial console', group: 'Serial' },
  { value: 'serial.list_ports', label: 'List COM ports', group: 'Serial' },
  { value: 'system.wait', label: 'Wait (seconds)', group: 'Utility' },
  { value: 'system.echo', label: 'Print a message', group: 'Utility' },
  { value: 'system.assert_contains', label: 'Verify text contains…', group: 'Utility' },
  { value: 'system.run_script', label: 'Run custom script (sandboxed)', group: 'Utility' },
  { value: 'system.run_file', label: 'Run a script/.exe file (with args)', group: 'Utility' },
  { value: 'system.run_command', label: 'Run a command line', group: 'Utility' },
  { value: 'system.run_registered', label: 'Run a registered script subcommand', group: 'Scripts' },
];

const LABELS = new Map(ACTION_OPTIONS.map((option) => [option.value, option.label]));

export function friendlyAction(action: string): string {
  return LABELS.get(action) ?? action;
}

/** Placeholder / helper text for common step parameters. */
export const PARAM_HINTS: Record<string, string> = {
  command: 'e.g. uname -a',
  expect_contains: 'pass only if the output contains this text',
  host: 'IP address, e.g. 192.168.1.10',
  port: 'port number',
  username: 'login user',
  working_dir: 'working directory on the target',
  seconds: 'how long to wait',
  message: 'text to print',
  text: 'text to check (can use {{steps.N.output}})',
  expected: 'text that must be present',
  lines: 'number of log lines',
  filter: 'logcat tag filter',
  local_path: 'path on this PC',
  remote_path: 'path on the target',
  apk_path: 'path to the .apk file',
  package: 'app package, e.g. com.example.app',
  duration: 'seconds to record',
  pattern: 'text/regex to look for',
  file_path: 'path to the file',
  script: 'script body',
  interpreter: 'python / powershell / bash',
  baudrate: 'e.g. 115200',
  attach_output: 'save this command’s full output as a report attachment',
  attach_name: 'attachment file name, e.g. journalctl',
  serial: 'device serial from Configuration',
  camera_name: 'camera name (blank = auto-detect first webcam)',
  output_path: 'where to save the file (blank = auto)',
  ffmpeg_path: 'path to ffmpeg.exe (blank = bundled/PATH)',
  state: 'state name',
  mount_point: 'e.g. /',
  cycle_delay: 'seconds between off and on',
  wait_timeout: 'max seconds to wait',
  reinstall: 'replace the app if installed',
  mode: 'camera: photo/video · adb reboot: bootloader/recovery',
  script_id: 'registered script id (Templates → Scripts)',
  args: 'arguments passed to the script, e.g. ["normal_power_cycle"]',
  command_timeout: 'seconds to allow the remote command',
  source_profile: 'source /etc/profile before the command (true/false)',
  raw_command: 'run the command verbatim, no PATH wrapping (Windows hosts)',
  strict_exit_code: 'fail on any non-zero exit (true/false)',
  reboot_command: 'command used to reboot, default: reboot',
  slog_command: 'QNX slog2info command, default: slog2info -b last',
  password: 'login password (stored only on the target/config, not the step)',
  key_file: 'path to a private key file',
  name: 'process / service name, e.g. sshd',
  match_file: 'file to scan for a pattern (e.g. your .dlt)',
  match_pattern: 'regex to find in the file, e.g. BootComplete',
  cwd: 'working directory',
};

export function prettyParamName(key: string): string {
  return key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

/** Settings most relevant to each action — powers the "add setting" dropdown. */
export const ACTION_PARAMS: Record<string, string[]> = {
  'ssh.execute_command': [
    'command', 'working_dir', 'command_timeout', 'attach_output', 'attach_name',
    'raw_command', 'source_profile', 'path', 'strict_exit_code', 'host', 'port',
    'username', 'domain', 'password', 'key_file',
  ],
  'ssh.upload_file': ['local_path', 'remote_path', 'host', 'port', 'username', 'password', 'key_file'],
  'ssh.download_file': ['remote_path', 'local_path', 'host', 'port', 'username', 'password', 'key_file'],
  'ssh.remount_rw': ['mount_point', 'command_timeout'],
  'ssh.file_exists': ['path', 'command_timeout'],
  'ssh.list_dir': ['path', 'attach_output', 'command_timeout'],
  'ssh.tail_file': ['path', 'lines', 'attach_output', 'command_timeout'],
  'ssh.process_status': ['name', 'command_timeout'],
  'ssh.reboot': ['reboot_command'],
  'ssh.capture_journal': ['lines', 'attach_name'],
  'ssh.capture_slog2info': ['slog_command', 'attach_name'],
  'adb.shell': ['command', 'serial', 'attach_output', 'attach_name'],
  'adb.push': ['local_path', 'remote_path', 'serial'],
  'adb.pull': ['local_path', 'remote_path', 'serial'],
  'adb.install_apk': ['apk_path', 'reinstall', 'serial'],
  'adb.uninstall_apk': ['package', 'serial'],
  'adb.logcat_dump': ['lines', 'filter', 'serial'],
  'adb.screenshot': ['local_path', 'serial'],
  'adb.screenrecord': ['duration', 'local_path', 'serial'],
  'adb.reboot': ['mode', 'serial'],
  'adb.wait_for_device': ['wait_timeout', 'serial'],
  'system.wait': ['seconds'],
  'system.echo': ['message'],
  'system.assert_contains': ['text', 'expected'],
  'system.run_script': ['interpreter', 'script'],
  'system.run_file': ['path', 'args', 'cwd', 'attach_output', 'match_file', 'match_pattern'],
  'system.run_command': ['command', 'cwd', 'attach_output'],
  'system.run_registered': ['script_id', 'args', 'attach_output', 'match_file', 'match_pattern'],
  'serial.wait_for_pattern': ['port', 'pattern', 'baudrate'],
  'serial.send': ['port', 'message', 'baudrate'],
  'serial.monitor': ['port', 'baudrate', 'duration'],
  'camera.capture': ['mode', 'camera_name', 'duration', 'output_path', 'ffmpeg_path'],
  'camera.capture_webcam': ['camera_name', 'output_path', 'ffmpeg_path'],
  'camera.record_video': ['camera_name', 'duration', 'output_path', 'ffmpeg_path'],
  'camera.screenshot': ['output_path'],
  'camera.detect': [],
  'camera.list_devices': ['ffmpeg_path'],
};

/** Suggested setting keys for an action (falls back to all known hints). */
export function paramsForAction(action: string): string[] {
  return ACTION_PARAMS[action] ?? Object.keys(PARAM_HINTS);
}
