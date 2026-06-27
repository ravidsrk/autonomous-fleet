import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

export default defineConfig({
  site: "https://autonomous-fleet.dev",
  integrations: [
    starlight({
      title: "autonomous-fleet",
      description:
        "Multi-agent engineering framework — install, missions, substrate, and reference.",
      logo: {
        alt: "autonomous-fleet",
        src: "./src/assets/logo.svg",
      },
      social: {
        github: "https://github.com/ravidsrk/autonomous-fleet",
      },
      customCss: ["./src/styles/custom.css"],
    }),
  ],
});