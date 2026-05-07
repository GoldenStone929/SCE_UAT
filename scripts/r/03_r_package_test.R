args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 1) {
  ROOT <- normalizePath(args[1], winslash = "/", mustWork = TRUE)
} else {
  ROOT <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

packages <- c(
  "dplyr",
  "tidyr",
  "readxl",
  "openxlsx",
  "officer",
  "flextable",
  "rmarkdown",
  "knitr",
  "ggplot2",
  "haven"
)

check_package <- function(pkg) {
  tryCatch(
    {
      if (!requireNamespace(pkg, quietly = TRUE)) {
        return(data.frame(
          language = "R",
          package = pkg,
          status = "NOT_AVAILABLE",
          version = "",
          error_message = "",
          stringsAsFactors = FALSE
        ))
      }
      data.frame(
        language = "R",
        package = pkg,
        status = "AVAILABLE",
        version = as.character(utils::packageVersion(pkg)),
        error_message = "",
        stringsAsFactors = FALSE
      )
    },
    error = function(e) {
      data.frame(
        language = "R",
        package = pkg,
        status = "ERROR",
        version = "",
        error_message = conditionMessage(e),
        stringsAsFactors = FALSE
      )
    }
  )
}

main <- function() {
  output_file <- file.path(ROOT, "outputs", "test_results", "r_package_availability.csv")
  dir.create(dirname(output_file), recursive = TRUE, showWarnings = FALSE)
  results <- do.call(rbind, lapply(packages, check_package))
  write.csv(results, output_file, row.names = FALSE, na = "")
  message("R package availability written to ", output_file)
}

tryCatch(
  {
    main()
  },
  error = function(e) {
    message("R package test failed: ", conditionMessage(e))
    quit(status = 1)
  }
)
