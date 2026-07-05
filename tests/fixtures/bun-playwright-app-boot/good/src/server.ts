import { createServer } from "node:http";

const sentinel = "actual-app-boot-ok";

const server = createServer((_request, response) => {
  response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  response.end(
    `<!doctype html><main data-testid="actual-app-boot-sentinel">${sentinel}</main>`,
  );
});

server.listen(4173, "127.0.0.1", () => {
  console.log("listening on http://127.0.0.1:4173/");
});
