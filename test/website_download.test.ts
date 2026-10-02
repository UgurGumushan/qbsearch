import { expect, spyOn, test } from "bun:test";
import { GET } from "../packages/website/app/download/latest/route";

test("legacy website download redirects to the stable ZIP without a network request", () => {
  const unexpectedFetch = Object.assign(
    () => {
      throw new Error("The download redirect must not make a network request");
    },
    { preconnect: globalThis.fetch.preconnect },
  );
  const fetchSpy = spyOn(globalThis, "fetch").mockImplementation(unexpectedFetch);

  try {
    const response = GET();
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://github.com/UgurGumushan/qbsearch/releases/latest/download/qbsearch-latest.zip",
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  } finally {
    fetchSpy.mockRestore();
  }
});
