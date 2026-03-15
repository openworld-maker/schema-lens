{{- define "schema-lens.name" -}}
schema-lens
{{- end -}}

{{- define "schema-lens.fullname" -}}
{{ include "schema-lens.name" . }}
{{- end -}}
