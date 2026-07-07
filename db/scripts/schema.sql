-- AI Recruiter Agent -- full database schema (PostgreSQL)
-- Generated from db/models.py -- this is a REFERENCE snapshot.
-- The actual source of truth is db/models.py + db/session.py::init_db()
-- (SQLAlchemy create_all()), which is what the app itself runs.
-- Regenerate this file after schema changes with:
--   python -m db.scripts.generate_schema_sql

CREATE TABLE configuration_snapshots (
	id SERIAL NOT NULL, 
	config_json JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	created_by VARCHAR, 
	notes TEXT, 
	PRIMARY KEY (id)
);

CREATE TABLE file_watch_state (
	id SERIAL NOT NULL, 
	file_path VARCHAR NOT NULL, 
	file_kind VARCHAR NOT NULL, 
	last_hash VARCHAR, 
	last_checked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE job_contacts (
	id SERIAL NOT NULL, 
	recruiter_email VARCHAR NOT NULL, 
	recruiter_name VARCHAR, 
	recruiter_company VARCHAR, 
	recruiter_phone VARCHAR, 
	recruiter_linkedin_url VARCHAR, 
	source_name VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE job_sources (
	id SERIAL NOT NULL, 
	source_name VARCHAR NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	source_type VARCHAR NOT NULL, 
	mode VARCHAR NOT NULL, 
	base_url VARCHAR, 
	last_run_at TIMESTAMP WITH TIME ZONE, 
	last_success_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR NOT NULL, 
	error_message TEXT, 
	consecutive_errors INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_name)
);

CREATE TABLE login_attempts (
	id SERIAL NOT NULL, 
	account_key VARCHAR NOT NULL, 
	failed_count INTEGER NOT NULL, 
	locked_until TIMESTAMP WITH TIME ZONE, 
	last_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE password_reset_tokens (
	id SERIAL NOT NULL, 
	account_type VARCHAR NOT NULL, 
	account_id INTEGER NOT NULL, 
	otp_hash VARCHAR NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	attempts INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	used_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE pending_actions (
	id SERIAL NOT NULL, 
	action_type VARCHAR NOT NULL, 
	reference_table VARCHAR NOT NULL, 
	reference_id INTEGER NOT NULL, 
	payload_summary TEXT, 
	status VARCHAR NOT NULL, 
	reviewed_by VARCHAR, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE profile_refreshes (
	id SERIAL NOT NULL, 
	source_name VARCHAR, 
	resume_file_path VARCHAR, 
	refresh_date DATE, 
	status VARCHAR, 
	error_message TEXT, 
	human_action_required BOOLEAN NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE push_subscriptions (
	id SERIAL NOT NULL, 
	owner_type VARCHAR NOT NULL, 
	owner_id INTEGER NOT NULL, 
	endpoint TEXT NOT NULL, 
	p256dh_key VARCHAR NOT NULL, 
	auth_key VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (endpoint)
);

CREATE TABLE stored_files (
	id SERIAL NOT NULL, 
	key VARCHAR NOT NULL, 
	content BYTEA NOT NULL, 
	content_type VARCHAR, 
	size_bytes INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE super_users (
	id SERIAL NOT NULL, 
	username VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE staff (
	id SERIAL NOT NULL, 
	username VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	created_by_superuser_id INTEGER, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_superuser_id) REFERENCES super_users (id)
);

CREATE TABLE organizations (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	created_by_staff_id INTEGER, 
	created_by_superuser_id INTEGER, 
	account_type VARCHAR NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	autonomous_email_enabled BOOLEAN NOT NULL, 
	initial_outreach_follow_up_days INTEGER NOT NULL, 
	client_submission_follow_up_days INTEGER NOT NULL, 
	post_interview_follow_up_days INTEGER NOT NULL, 
	resubmission_cooldown_days INTEGER NOT NULL, 
	inbox_poll_interval_minutes INTEGER NOT NULL, 
	max_failed_login_attempts INTEGER NOT NULL, 
	lockout_minutes INTEGER NOT NULL, 
	email_notifications_enabled BOOLEAN NOT NULL, 
	max_jobs_per_day INTEGER NOT NULL, 
	max_applications_per_day INTEGER NOT NULL, 
	max_emails_per_day INTEGER NOT NULL, 
	send_only_business_hours BOOLEAN NOT NULL, 
	business_hours_start_hour INTEGER NOT NULL, 
	business_hours_end_hour INTEGER NOT NULL, 
	business_hours_timezone VARCHAR NOT NULL, 
	trial_expires_at DATE, 
	trial_reminder_sent_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_staff_id) REFERENCES staff (id), 
	FOREIGN KEY(created_by_superuser_id) REFERENCES super_users (id)
);

CREATE TABLE candidates (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	slug VARCHAR NOT NULL, 
	full_name VARCHAR NOT NULL, 
	availability_status VARCHAR NOT NULL, 
	login_email VARCHAR, 
	password_hash VARCHAR, 
	profile_status VARCHAR NOT NULL, 
	approved_profile_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, slug), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE invites (
	id SERIAL NOT NULL, 
	email VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	organization_id INTEGER NOT NULL, 
	invited_by_type VARCHAR NOT NULL, 
	invited_by_id INTEGER NOT NULL, 
	otp_hash VARCHAR NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	attempts INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	used_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE admin_users (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	username VARCHAR NOT NULL, 
	email VARCHAR, 
	password_hash VARCHAR NOT NULL, 
	linked_candidate_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	FOREIGN KEY(linked_candidate_id) REFERENCES candidates (id)
);

CREATE TABLE candidate_documents (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	document_type VARCHAR NOT NULL, 
	file_name VARCHAR NOT NULL, 
	storage_key VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	uploaded_by VARCHAR NOT NULL, 
	reviewed_by VARCHAR, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id)
);

CREATE TABLE candidate_operational_configs (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	search_config_json JSON, 
	strict_skill_match_required BOOLEAN NOT NULL, 
	send_mode VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (candidate_id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id)
);

CREATE TABLE candidate_profile_submissions (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	submitted_profile_json JSON NOT NULL, 
	resume_uploaded BOOLEAN NOT NULL, 
	status VARCHAR NOT NULL, 
	reviewed_by VARCHAR, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id)
);

CREATE TABLE email_account_credentials (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	provider VARCHAR NOT NULL, 
	account_email VARCHAR NOT NULL, 
	secret_type VARCHAR NOT NULL, 
	encrypted_secret TEXT NOT NULL, 
	scopes_granted JSON, 
	status VARCHAR NOT NULL, 
	last_error TEXT, 
	connected_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (candidate_id, provider), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id)
);

CREATE TABLE jobs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	candidate_id INTEGER, 
	source_id INTEGER, 
	source_name VARCHAR NOT NULL, 
	external_job_id VARCHAR, 
	job_title VARCHAR NOT NULL, 
	company_name VARCHAR, 
	location VARCHAR, 
	work_mode VARCHAR, 
	employment_type VARCHAR, 
	c2c_mentioned BOOLEAN, 
	w2_mentioned BOOLEAN, 
	sponsorship_status VARCHAR, 
	job_url VARCHAR, 
	post_url VARCHAR, 
	description_text TEXT, 
	authorization_text TEXT, 
	salary_or_rate VARCHAR, 
	job_contact_id INTEGER, 
	role_classification JSON, 
	discovered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	last_checked_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR NOT NULL, 
	skip_reason TEXT, 
	dedup_hash VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (candidate_id, source_id, external_job_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id), 
	FOREIGN KEY(source_id) REFERENCES job_sources (id), 
	FOREIGN KEY(job_contact_id) REFERENCES job_contacts (id)
);

CREATE TABLE resume_ingestion_runs (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	resume_file_path VARCHAR NOT NULL, 
	file_hash VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	new_skills_suggested INTEGER NOT NULL, 
	error_message TEXT, 
	triggered_by VARCHAR NOT NULL, 
	resume_approval_status VARCHAR NOT NULL, 
	pending_storage_key VARCHAR, 
	active_storage_key VARCHAR, 
	resume_approved_by VARCHAR, 
	resume_approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id)
);

CREATE TABLE subscriptions (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	monthly_rate NUMERIC(10, 2), 
	currency VARCHAR NOT NULL, 
	paused_by VARCHAR, 
	paused_at TIMESTAMP WITH TIME ZONE, 
	resumed_at TIMESTAMP WITH TIME ZONE, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	current_period_start DATE, 
	current_period_end DATE, 
	trial_reminder_sent_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (candidate_id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE application_status (
	id SERIAL NOT NULL, 
	job_id INTEGER NOT NULL, 
	status VARCHAR, 
	submitted_to_client BOOLEAN NOT NULL, 
	client_name VARCHAR, 
	rate_discussed VARCHAR, 
	rate_submitted VARCHAR, 
	last_contact_date DATE, 
	next_action_date DATE, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id)
);

CREATE TABLE applications (
	id SERIAL NOT NULL, 
	job_id INTEGER NOT NULL, 
	source_name VARCHAR, 
	application_url VARCHAR, 
	application_method VARCHAR, 
	resume_file_path VARCHAR, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR NOT NULL, 
	error_message TEXT, 
	human_review_required BOOLEAN NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id)
);

CREATE TABLE emails (
	id SERIAL NOT NULL, 
	candidate_id INTEGER, 
	job_id INTEGER NOT NULL, 
	job_contact_id INTEGER, 
	to_email VARCHAR, 
	from_email VARCHAR, 
	subject VARCHAR, 
	body TEXT, 
	resume_file_path VARCHAR, 
	gmail_object_id VARCHAR, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR NOT NULL, 
	pipeline_stage VARCHAR, 
	submitted_to_client_at TIMESTAMP WITH TIME ZONE, 
	pipeline_notes TEXT, 
	error_message TEXT, 
	reply_received BOOLEAN NOT NULL, 
	last_reply_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id), 
	FOREIGN KEY(job_contact_id) REFERENCES job_contacts (id)
);

CREATE TABLE resume_versions (
	id SERIAL NOT NULL, 
	candidate_id INTEGER, 
	job_id INTEGER NOT NULL, 
	target_role VARCHAR, 
	company_name VARCHAR, 
	file_name VARCHAR, 
	file_path VARCHAR, 
	tailoring_summary TEXT, 
	risk_notes TEXT, 
	grounding_flags TEXT, 
	confidence_score NUMERIC(3, 2), 
	human_review_required BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id)
);

CREATE TABLE skill_inventory_items (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	skill_name VARCHAR NOT NULL, 
	tier VARCHAR NOT NULL, 
	source_bullet TEXT, 
	source_project_or_role VARCHAR, 
	suggested_by VARCHAR NOT NULL, 
	confidence NUMERIC(3, 2), 
	status VARCHAR NOT NULL, 
	reviewed_by VARCHAR, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_notes TEXT, 
	ingestion_run_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id), 
	FOREIGN KEY(ingestion_run_id) REFERENCES resume_ingestion_runs (id)
);

CREATE TABLE system_logs (
	id SERIAL NOT NULL, 
	event_type VARCHAR, 
	source_name VARCHAR, 
	job_id INTEGER, 
	message TEXT, 
	error_details TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id)
);

CREATE TABLE client_submissions (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	email_id INTEGER, 
	end_client_name VARCHAR NOT NULL, 
	end_client_name_normalized VARCHAR NOT NULL, 
	implementation_partner_name VARCHAR, 
	location VARCHAR, 
	location_normalized VARCHAR, 
	submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id), 
	FOREIGN KEY(email_id) REFERENCES emails (id)
);

CREATE TABLE follow_ups (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	job_id INTEGER NOT NULL, 
	email_id INTEGER, 
	follow_up_type VARCHAR NOT NULL, 
	next_follow_up_date DATE, 
	follow_up_count INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	last_follow_up_sent_at TIMESTAMP WITH TIME ZONE, 
	stop_reason TEXT, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id), 
	FOREIGN KEY(email_id) REFERENCES emails (id)
);

CREATE TABLE interviews (
	id SERIAL NOT NULL, 
	email_id INTEGER NOT NULL, 
	round_name VARCHAR, 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(email_id) REFERENCES emails (id)
);
