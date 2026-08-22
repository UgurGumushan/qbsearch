export interface LiveArguments {
  timeout: number;
  skipSafety: boolean;
  installOnly: boolean;
  query: string | null;
  category: string;
  contentCategory: string;
  pluginIds: string[] | null;
  allowEmpty: boolean;
  requireResults: boolean;
}

const VALUE_OPTIONS = new Set([
  "--timeout",
  "--query",
  "--category",
  "--content-category",
  "--plugin",
]);

export function liveUsage(): string {
  return `Usage: bun run test:live[:watch] -- [options]

Options:
  --timeout SECONDS       Per-plugin process timeout (default: 120)
  --skip-safety           Skip the local safety helper suite
  --install-only          Validate metadata and search contracts without requests
  --query QUERY           Use one query for every plugin
  --category CATEGORY     qBittorrent category (default: all)
  --content-category CAT  Limit tests to a catalog content category (default: all)
  --plugin ID             Test only this plugin; may be repeated
  --allow-empty           Accept live searches that return no results
  --require-results       Fail live searches that return no results
`;
}

function parseNumber(value: string, option: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${option} requires a number`);
  }
  return parsed;
}

export function parseLiveArguments(rawArgs: string[]): LiveArguments | null {
  const args: LiveArguments = {
    timeout: 120,
    skipSafety: false,
    installOnly: false,
    query: null,
    category: "all",
    contentCategory: "all",
    pluginIds: null,
    allowEmpty: false,
    requireResults: false,
  };
  const pluginIds: string[] = [];

  for (let index = 0; index < rawArgs.length; index += 1) {
    const argument = rawArgs[index];
    if (argument === "--help" || argument === "-h") {
      console.log(liveUsage());
      return null;
    }
    if (argument === "--skip-safety") {
      args.skipSafety = true;
      continue;
    }
    if (argument === "--install-only") {
      args.installOnly = true;
      continue;
    }
    if (argument === "--allow-empty") {
      args.allowEmpty = true;
      continue;
    }
    if (argument === "--require-results") {
      args.requireResults = true;
      continue;
    }

    const separator = argument.indexOf("=");
    const option = separator < 0 ? argument : argument.slice(0, separator);
    const inlineValue = separator < 0 ? undefined : argument.slice(separator + 1);
    const value = inlineValue ?? rawArgs.at(index + 1);
    if (VALUE_OPTIONS.has(option)) {
      if (!value || (inlineValue === undefined && value.startsWith("-"))) {
        throw new Error(`${option} requires a value`);
      }
      if (inlineValue === undefined) {
        index += 1;
      }
      switch (option) {
        case "--timeout":
          args.timeout = parseNumber(value, option);
          break;
        case "--query":
          args.query = value;
          break;
        case "--category":
          args.category = value;
          break;
        case "--content-category":
          args.contentCategory = value;
          break;
        case "--plugin":
          pluginIds.push(value);
          break;
      }
      continue;
    }
    throw new Error(`unrecognized argument: ${argument}`);
  }

  args.pluginIds = pluginIds.length > 0 ? pluginIds : null;
  return args;
}
