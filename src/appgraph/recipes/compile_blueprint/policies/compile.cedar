// compile.cedar: may compile_blueprint write the blueprint(s) (and a tech-profile draft) to this folder?
// write_ok: absolute and under the user's home or the temporary folder (appgraph.build.steps.write_root_ok).
permit (principal == Service::"app-graph", action == Action::"compile_blueprint", resource) when { context.write_ok };
