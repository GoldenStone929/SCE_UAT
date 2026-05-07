args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 1) {
  ROOT <- normalizePath(args[1], winslash = "/", mustWork = TRUE)
} else {
  ROOT <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

main <- function() {
  output_dir <- file.path(ROOT, "outputs", "r")
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  output_file <- file.path(output_dir, "r_smoke_test.txt")
  timestamp <- format(Sys.time(), "%Y-%m-%dT%H:%M:%S")

  writeLines(
    c(
      "R smoke test PASS",
      paste("Timestamp:", timestamp),
      paste("Root:", ROOT)
    ),
    con = output_file
  )

  message("R smoke test completed successfully.")
}

tryCatch(
  {
    main()
  },
  error = function(e) {
    message("R smoke test failed: ", conditionMessage(e))
    quit(status = 1)
  }
)
