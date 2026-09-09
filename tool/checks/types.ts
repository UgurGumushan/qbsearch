export type CheckScope = "check" | "checkStrict" | "static" | "staticStrict" | "python";

export interface CheckTask {
  label: string;
  command: string[];
}

export type CheckResult = CheckTask & {
  exitCode: number;
};
