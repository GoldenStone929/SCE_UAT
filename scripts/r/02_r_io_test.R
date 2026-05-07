args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 1) {
  ROOT <- normalizePath(args[1], winslash = "/", mustWork = TRUE)
} else {
  ROOT <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

file_ok <- function(path) {
  file.exists(path) && file.info(path)$size > 0
}

main <- function() {
  input_file <- file.path(ROOT, "data", "input", "fake_dm.csv")
  output_dir <- file.path(ROOT, "outputs", "r")
  log_file <- file.path(ROOT, "outputs", "logs", "r_io_append.log")
  subfolder <- file.path(output_dir, "io_subfolder")
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(log_file), recursive = TRUE, showWarnings = FALSE)
  dir.create(subfolder, recursive = TRUE, showWarnings = FALSE)

  dm <- read.csv(input_file, stringsAsFactors = FALSE)
  if (nrow(dm) <= 0) {
    stop("No rows read from fake_dm.csv")
  }

  csv_out <- file.path(output_dir, "r_io_dm_copy.csv")
  txt_out <- file.path(output_dir, "r_io_test.txt")
  timestamp <- format(Sys.time(), "%Y-%m-%dT%H:%M:%S")

  write.csv(dm, csv_out, row.names = FALSE)
  writeLines(
    c(
      "R file I/O test PASS",
      paste("Timestamp:", timestamp),
      paste("Rows read:", nrow(dm))
    ),
    con = txt_out
  )
  cat(paste(timestamp, "- R append test completed\n"), file = log_file, append = TRUE)

  read_back <- read.csv(csv_out, stringsAsFactors = FALSE)
  evidence_files <- c(csv_out, txt_out, log_file)
  bad_files <- evidence_files[!vapply(evidence_files, file_ok, logical(1))]
  if (length(bad_files) > 0) {
    stop(paste("Generated files missing or empty:", paste(bad_files, collapse = "; ")))
  }
  if (nrow(read_back) != nrow(dm)) {
    stop("Read-back row count did not match source row count")
  }

  message("R I/O test completed successfully.")
}

tryCatch(
  {
    main()
  },
  error = function(e) {
    message("R I/O test failed: ", conditionMessage(e))
    quit(status = 1)
  }
)
