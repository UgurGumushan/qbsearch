export interface LiveWorkerArguments {
  plugin: string;
  query: string;
  category: string;
  allowEmpty: boolean;
  installOnly: boolean;
}

export interface LiveResponse {
  url: string;
  status: number;
  body: string;
  contentType: string;
  attempts: number;
}

export interface LivePluginContract {
  id: string;
  name: string;
  siteUrl: string;
  version: string;
  source: string;
  errors: string[];
}

export interface LiveProbeReport {
  id: string;
  query: string;
  category: string;
  requests: number;
  resultMarkers: number;
  url: string | null;
  status: number | null;
  mode: "probe" | "install-only";
}
