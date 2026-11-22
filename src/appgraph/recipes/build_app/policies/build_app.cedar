// build_app.cedar: may this system build write its components, their scaffolds and config, and the system README, and
// run the integration (the backend and the acceptance tests, in a container with no network)?
// write_ok: every component's output folder and the README's folder are absolute and under the user's home or the
// temporary folder (appgraph.build.steps.write_root_ok). profiles_ok: every component names a known tech profile.
permit (
    principal == Service::"app-graph",
    action == Action::"build_app",
    resource
) when { context.write_ok && context.profiles_ok };
