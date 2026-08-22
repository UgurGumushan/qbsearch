export type CheckScope = "check" | "static" | "python";

export interface CheckTask {
  label: string;
  command: string[];
}

export type CheckResult = CheckTask & {
  exitCode: number;
};
