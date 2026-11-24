import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function response(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => body,
  } as Response;
}

describe("VibeMatch text playlist flow", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("vibematch.session_id", "local-session-1234");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/catalog/genres")) return response(["Ambient", "Electronic"]);
      if (url.endsWith("/api/v1/images/interpret")) return response({ caption: "A cloudy lake", review_required: true, image_retained: false, model_id: "Salesforce/blip-image-captioning-base" });
      if (url.includes("/api/v1/preferences/")) return response({ session_id: "local-session-1234", preferred_genres: [] });
      if (url.endsWith("/api/v1/playlists")) return response({
        playlist_id: "playlist-1",
        prompt: "quiet ambient music",
        recommendations: [{
          catalog_id: "track-1",
          title: "Soft Horizon",
          artist: "A. Musician",
          source_url: "https://example.org/track-1",
          license: "CC0 1.0 Universal",
          license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
          genres: ["Ambient"],
          score: 0.7,
          content_similarity: 0.7,
          preference_match: 0,
          liked_genre_match: 0,
          reasons: ["Matches catalog genres: Ambient"],
        }],
      });
      return response({ saved: true });
    }));
  });

  it("generates and displays recommendations with their explanation and source", async () => {
    render(<App />);
    const prompt = screen.getByLabelText("Describe your vibe");
    fireEvent.change(prompt, { target: { value: "quiet ambient music" } });
    fireEvent.click(screen.getByRole("button", { name: /make me a playlist/i }));

    expect(await screen.findByRole("heading", { name: "Soft Horizon" })).toBeInTheDocument();
    expect(screen.getByText("Matches catalog genres: Ambient")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Listen ↗" })).toHaveAttribute("href", "https://example.org/track-1");
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/v1/playlists", expect.any(Object)));
  });

  it("puts an image caption in the editable prompt before playlist generation", async () => {
    render(<App />);
    const imageInput = screen.getByLabelText("Choose an image");
    fireEvent.change(imageInput, { target: { files: [new File(["image"], "scene.png", { type: "image/png" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Suggest a description" }));
    const prompt = screen.getByLabelText("Describe your vibe") as HTMLTextAreaElement;
    await waitFor(() => expect(prompt.value).toBe("A cloudy lake"));
    expect(screen.getByRole("status")).toHaveTextContent("Review and edit");
    expect(fetch).toHaveBeenCalledWith("/api/v1/images/interpret", expect.objectContaining({ method: "POST", body: expect.any(FormData) }));
  });
});
