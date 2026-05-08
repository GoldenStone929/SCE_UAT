args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 1) {
  ROOT <- normalizePath(args[1], winslash = "/", mustWork = TRUE)
} else {
  ROOT <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

add_result <- function(results, output_type, file_path, status, package_used = "", error_message = "") {
  rbind(
    results,
    data.frame(
      language = "R",
      output_type = output_type,
      file_path = file_path,
      status = status,
      package_used = package_used,
      error_message = error_message,
      stringsAsFactors = FALSE
    )
  )
}

file_ok <- function(path) {
  file.exists(path) && file.info(path)$size > 0
}

main <- function() {
  output_dir <- file.path(ROOT, "outputs", "r", "generated_documents")
  result_file <- file.path(ROOT, "outputs", "test_results", "r_document_generation_results.csv")
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  dir.create(dirname(result_file), recursive = TRUE, showWarnings = FALSE)
  timestamp <- format(Sys.time(), "%Y-%m-%dT%H:%M:%S")
  markdown_lines <- c(
    "# R Document Generation Test",
    "",
    paste("- Timestamp:", timestamp),
    "- Status: PASS",
    "- Runtime: R",
    "- Purpose: verify that the SCE can create readable R-generated output artifacts.",
    "",
    "## Generated Baseline Formats",
    "",
    "- TXT",
    "- CSV",
    "- HTML",
    "- Markdown",
    ""
  )
  results <- data.frame(
    language = character(),
    output_type = character(),
    file_path = character(),
    status = character(),
    package_used = character(),
    error_message = character(),
    stringsAsFactors = FALSE
  )

  path <- file.path(output_dir, "r_document_test.txt")
  tryCatch(
    {
      writeLines(c("R TXT document generation PASS", paste("Timestamp:", timestamp)), path)
      results <- add_result(results, "TXT", path, ifelse(file_ok(path), "PASS", "FAIL"), "base")
    },
    error = function(e) {
      results <<- add_result(results, "TXT", "", "ERROR", "base", conditionMessage(e))
    }
  )

  path <- file.path(output_dir, "r_document_test.csv")
  tryCatch(
    {
      write.csv(data.frame(item = c("timestamp", "status"), value = c(timestamp, "PASS")), path, row.names = FALSE)
      results <- add_result(results, "CSV", path, ifelse(file_ok(path), "PASS", "FAIL"), "base")
    },
    error = function(e) {
      results <<- add_result(results, "CSV", "", "ERROR", "base", conditionMessage(e))
    }
  )

  path <- file.path(output_dir, "r_document_test.html")
  tryCatch(
    {
      writeLines(
        c(
          "<!doctype html><html><head><meta charset='utf-8'><title>R Document Test</title></head><body>",
          "<h1>R Document Test</h1>",
          paste0("<p>", timestamp, "</p>"),
          "</body></html>"
        ),
        path
      )
      results <- add_result(results, "HTML", path, ifelse(file_ok(path), "PASS", "FAIL"), "base")
    },
    error = function(e) {
      results <<- add_result(results, "HTML", "", "ERROR", "base", conditionMessage(e))
    }
  )

  path <- file.path(output_dir, "r_document_test.md")
  tryCatch(
    {
      writeLines(markdown_lines, path)
      results <- add_result(results, "MARKDOWN", path, ifelse(file_ok(path), "PASS", "FAIL"), "base")
    },
    error = function(e) {
      results <<- add_result(results, "MARKDOWN", "", "ERROR", "base", conditionMessage(e))
    }
  )

  if (requireNamespace("openxlsx", quietly = TRUE)) {
    path <- file.path(output_dir, "r_document_test.xlsx")
    tryCatch(
      {
        workbook <- openxlsx::createWorkbook()
        openxlsx::addWorksheet(workbook, "UAT")
        openxlsx::writeData(workbook, "UAT", data.frame(item = c("timestamp", "status"), value = c(timestamp, "PASS")))
        openxlsx::saveWorkbook(workbook, path, overwrite = TRUE)
        results <- add_result(results, "XLSX", path, ifelse(file_ok(path), "PASS", "FAIL"), "openxlsx")
      },
      error = function(e) {
        results <<- add_result(results, "XLSX", "", "ERROR", "openxlsx", conditionMessage(e))
      }
    )
  } else {
    results <- add_result(results, "XLSX", "", "NOT_AVAILABLE", "openxlsx")
  }

  if (requireNamespace("officer", quietly = TRUE)) {
    path <- file.path(output_dir, "r_document_test.docx")
    tryCatch(
      {
        doc <- officer::read_docx()
        doc <- officer::body_add_par(doc, "R Document Test", style = "heading 1")
        doc <- officer::body_add_par(doc, paste("Timestamp:", timestamp))
        print(doc, target = path)
        results <- add_result(results, "DOCX", path, ifelse(file_ok(path), "PASS", "FAIL"), "officer")
      },
      error = function(e) {
        results <<- add_result(results, "DOCX", "", "ERROR", "officer", conditionMessage(e))
      }
    )
  } else {
    results <- add_result(results, "DOCX", "", "NOT_AVAILABLE", "officer")
  }

  path <- file.path(output_dir, "r_document_test.pdf")
  tryCatch(
    {
      grDevices::pdf(path, width = 8.5, height = 11)
      par(mar = c(1, 1, 1, 1))
      plot.new()
      title("R Document Generation Test")
      y <- 0.92
      for (line in markdown_lines[3:length(markdown_lines)]) {
        wrapped <- strwrap(line, width = 88)
        if (length(wrapped) == 0) {
          wrapped <- ""
        }
        for (text_line in wrapped) {
          text(0.05, y, text_line, adj = c(0, 1), cex = 0.82, family = "mono")
          y <- y - 0.045
          if (y < 0.08) {
            plot.new()
            y <- 0.92
          }
        }
      }
      grDevices::dev.off()
      results <- add_result(results, "PDF", path, ifelse(file_ok(path), "PASS", "FAIL"), "base_pdf")
    },
    error = function(e) {
      if (grDevices::dev.cur() > 1) {
        grDevices::dev.off()
      }
      results <<- add_result(results, "PDF", "", "ERROR", "base_pdf", conditionMessage(e))
    }
  )

  if (requireNamespace("rmarkdown", quietly = TRUE)) {
    rmd_path <- file.path(output_dir, "r_document_test_rmarkdown.Rmd")
    html_path <- file.path(output_dir, "r_document_test_rmarkdown.html")
    tryCatch(
      {
        writeLines(
          c(
            "---",
            "title: R Markdown Document Test",
            "output: html_document",
            "---",
            "",
            paste("Timestamp:", timestamp)
          ),
          rmd_path
        )
        rmarkdown::render(rmd_path, output_file = basename(html_path), output_dir = output_dir, quiet = TRUE)
        results <- add_result(results, "RMARKDOWN_HTML", html_path, ifelse(file_ok(html_path), "PASS", "FAIL"), "rmarkdown")
      },
      error = function(e) {
        results <<- add_result(results, "RMARKDOWN_HTML", "", "ERROR", "rmarkdown", conditionMessage(e))
      }
    )
  } else {
    results <- add_result(results, "RMARKDOWN_HTML", "", "NOT_AVAILABLE", "rmarkdown")
  }

  write.csv(results, result_file, row.names = FALSE, na = "")
  baseline <- results$status[results$output_type %in% c("TXT", "CSV", "HTML", "MARKDOWN")]
  message("R document generation results written to ", result_file)
  if (!all(baseline == "PASS")) {
    quit(status = 1)
  }
}

tryCatch(
  {
    main()
  },
  error = function(e) {
    message("R document generation failed: ", conditionMessage(e))
    quit(status = 1)
  }
)
