/**
 * Define inputs and reports exchanged by live probe workers.
 * @file
 */
/** Validated options for one plugin probe process. */
export interface LiveWorkerArguments {
  plugin: string;
  query: string;
  category: string;
  allowEmpty: boolean;
  installOnly: boolean;
}

/** Decoded response and transport metadata recorded by a live probe. */
export interface LiveResponse {
  url: string;
  status: number;
  body: string;
  contentType: string;
  attempts: number;
  retryAfter?: string;
  bytes?: number;
}

/** Static engine metadata and validation errors used before contacting an endpoint. */
export interface LivePluginContract {
  id: string;
  name: string;
  siteUrl: string;
  version: string;
  source: string;
  errors: string[];
}

/** Installability or network-probe evidence emitted by a plugin worker. */
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
