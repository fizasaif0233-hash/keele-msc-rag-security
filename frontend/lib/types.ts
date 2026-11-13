export type Role = "admin" | "employee" | "researcher";

export type Profile = {
  id: string;
  email: string;
  role: Role;
  created_at: string | null;
  can_upload?: boolean;
};

export type MetricSummary = {
  completed_trials: number;
  excluded_infrastructure_failures: number;
  attack_trials: number;
  attack_successes: number;
  attack_success_rate: number | null;
  disclosure_count: number;
  disclosure_rate: number | null;
  benign_trials: number;
  legitimate_successes: number;
  legitimate_task_success_rate: number | null;
  average_latency_ms: number | null;
  median_latency_ms: number | null;
  p95_latency_ms: number | null;
  outcome_counts: Record<string, number>;
  has_results?: boolean;
};

export type Reduction = {
  percentage_reduction: number | null;
  absolute_reduction: number | null;
  note: string | null;
};

export type Report = {
  has_results: boolean;
  trial_count: number;
  by_configuration: Record<"baseline" | "secured", MetricSummary>;
  reductions: {
    attack_success_rate: Reduction;
    disclosure_rate: Reduction;
    legitimate_task_success_rate: { absolute_difference: number | null };
    average_latency_ms: { absolute_difference: number | null };
  } | null;
  category_breakdown: Array<{
    category: string;
    configuration: string;
    attack_success_rate: number | null;
    disclosure_rate: number | null;
    legitimate_task_success_rate: number | null;
    completed_trials: number;
    attack_trials: number;
    benign_trials: number;
  }>;
  outcome_distribution: Array<{ configuration: string; outcome: string; count: number }>;
};

export type Experiment = {
  id: string;
  name: string;
  configuration: string;
  dataset_id: string;
  repetitions: number;
  status: string;
  parameters: Record<string, unknown>;
  comparison_group: string | null;
  started_at: string | null;
  completed_at: string | null;
  progress_completed: number;
  progress_total: number;
  error_message: string | null;
  created_at: string | null;
};

export type DocumentRecord = {
  id: string;
  owner_id: string;
  owner_email: string | null;
  title: string;
  document_type: string;
  access_level: string;
  processing_status: string;
  error_message: string | null;
  chunk_count: number;
  protected_markers: string[];
  created_at: string | null;
  extracted_text?: string;
};

export type SecurityEvent = {
  id: string;
  user_email: string | null;
  event_type: string;
  severity: string;
  outcome: string;
  configuration: string | null;
  experiment_id: string | null;
  test_case_id: string | null;
  created_at: string | null;
};

export type TestCaseRecord = {
  id: string;
  dataset_id: string;
  category: string;
  title: string;
  description: string;
  input: string;
  expected_outcome: string;
  evaluation_criteria: Record<string, unknown>;
  created_at: string | null;
};
