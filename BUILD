load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

# Master pipeline runner - coordinates all pipeline steps
py_binary(
    name = "pipeline",
    srcs = ["run_pipeline.py"],
    main = "run_pipeline.py",
    deps = ["//pipeline:core"],
)

py_library(
    name = "scenelens",
    deps = [
        "//pipeline:core",
        "//backend:api", 
        "//ui:streamlit_app",
    ],
)