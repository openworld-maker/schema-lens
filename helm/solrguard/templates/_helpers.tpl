{{- define "solrguard.name" -}}
solrguard
{{- end -}}

{{- define "solrguard.fullname" -}}
{{ include "solrguard.name" . }}
{{- end -}}
