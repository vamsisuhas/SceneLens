load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

# Core pipeline library with database models
py_library(
    name = "core",
    srcs = [
        "database.py", 
        "models.py",
    ],
# No deps needed - using system packages
)

# Video ingestion
py_binary(
    name = "ingest",
    srcs = ["ingest.py"],
    main = "ingest.py",
    deps = [":core"],
)

# Keyframe extraction  
py_binary(
    name = "keyframe",
    srcs = ["keyframe.py"],
    main = "keyframe.py",
    deps = [":core"],
)

# Caption generation
py_binary(
    name = "captions",
    srcs = ["captions.py"],
    main = "captions.py",
    deps = [":core"],
)

# Vision embeddings
py_binary(
    name = "vision_embed", 
    srcs = ["vision_embed.py"],
    main = "vision_embed.py",
    deps = [":core"],
)

# FAISS indexing
py_binary(
    name = "fuse_index",
    srcs = ["fuse_index.py"],
    main = "fuse_index.py",
    deps = [":core"],
)