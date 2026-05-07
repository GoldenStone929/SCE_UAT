args <- commandArgs(trailingOnly = TRUE)

if (length(args) >= 1) {
  ROOT <- normalizePath(args[1], winslash = "/", mustWork = TRUE)
} else {
  ROOT <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

related_values <- c("RELATED", "POSSIBLY RELATED", "PROBABLY RELATED")

read_expected <- function(path) {
  expected <- read.csv(path, stringsAsFactors = FALSE)
  names(expected) <- c("metric", "expected_value")
  expected
}

write_metric_csv <- function(path, metrics) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  output <- data.frame(
    metric = names(metrics),
    actual_value = as.character(metrics),
    stringsAsFactors = FALSE
  )
  write.csv(output, path, row.names = FALSE, na = "")
}

is_non_numeric <- function(values) {
  converted <- suppressWarnings(as.numeric(values))
  is.na(converted)
}

validate_metrics <- function(metrics, expected) {
  actual <- data.frame(
    metric = names(metrics),
    actual_value = as.character(metrics),
    stringsAsFactors = FALSE
  )
  merged <- merge(expected, actual, by = "metric", all.x = TRUE, sort = FALSE)
  merged$actual_value[is.na(merged$actual_value)] <- ""
  merged$status <- ifelse(
    as.character(merged$expected_value) == as.character(merged$actual_value),
    "PASS",
    "FAIL"
  )
  merged[, c("metric", "expected_value", "actual_value", "status")]
}

main <- function() {
  ae <- read.csv(file.path(ROOT, "data", "input", "fake_ae.csv"), stringsAsFactors = FALSE)
  lb <- read.csv(file.path(ROOT, "data", "input", "fake_lb.csv"), stringsAsFactors = FALSE)

  ae_metrics <- c(
    total_ae_records = nrow(ae),
    subjects_with_ae = length(unique(ae$USUBJID[ae$USUBJID != ""])),
    serious_ae_records = sum(toupper(ae$AESER) == "Y"),
    treatment_related_ae_records = sum(toupper(ae$AEREL) %in% related_values),
    severe_ae_records = sum(toupper(ae$AESEV) == "SEVERE"),
    ae_start_after_end_records = sum(ae$AESTDTC != "" & ae$AEENDTC != "" & ae$AESTDTC > ae$AEENDTC)
  )

  lb_metrics <- c(
    total_lb_records = nrow(lb),
    alt_high_records = sum(toupper(lb$LBTEST) == "ALT" & toupper(lb$LBNRIND) == "HIGH"),
    ast_high_records = sum(toupper(lb$LBTEST) == "AST" & toupper(lb$LBNRIND) == "HIGH"),
    missing_lab_unit_records = sum(is.na(lb$LBORRESU) | trimws(lb$LBORRESU) == ""),
    non_numeric_lab_result_records = sum(is_non_numeric(lb$LBORRES)),
    abnormal_high_lab_records = sum(toupper(lb$LBNRIND) == "HIGH")
  )

  ae_output <- file.path(ROOT, "outputs", "r", "ae_summary_from_r.csv")
  lb_output <- file.path(ROOT, "outputs", "r", "lb_summary_from_r.csv")
  validation_output <- file.path(ROOT, "outputs", "test_results", "r_clinical_validation.csv")

  write_metric_csv(ae_output, ae_metrics)
  write_metric_csv(lb_output, lb_metrics)

  ae_expected <- read_expected(file.path(ROOT, "data", "expected", "expected_ae_summary.csv"))
  lb_expected <- read_expected(file.path(ROOT, "data", "expected", "expected_lb_summary.csv"))
  validation <- rbind(
    validate_metrics(ae_metrics, ae_expected),
    validate_metrics(lb_metrics, lb_expected)
  )

  dir.create(dirname(validation_output), recursive = TRUE, showWarnings = FALSE)
  write.csv(validation, validation_output, row.names = FALSE, na = "")

  status <- if (all(validation$status == "PASS")) "PASS" else "FAIL"
  message("R clinical validation status: ", status)
  if (status != "PASS") {
    quit(status = 1)
  }
}

tryCatch(
  {
    main()
  },
  error = function(e) {
    message("R clinical summary failed: ", conditionMessage(e))
    quit(status = 1)
  }
)
