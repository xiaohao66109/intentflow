export function encodeField(value: unknown, schema: any): string {
  if(schema.type !== 'array') return String(value ?? '')
  return ((value ?? []) as unknown[]).map(v=> schema.items.type === 'array' ? JSON.stringify(v) : String(v)).join('\n')
}
export function decodeField(value: string, schema: any): unknown {
  if(schema.type !== 'array') return value.trim()
  const lines = value.split('\n').map(s=>s.trim()).filter(Boolean)
  return schema.items.type === 'array' ? lines.map(s=>JSON.parse(s)) : lines
}

// A required JSON property may still accept an empty string or empty list.
export function needsValue(schema: any): boolean {
  return schema.minLength > 0 || schema.minItems > 0 || !!schema.enum?.length
}

export function editableFields(schema: any): [string, any][] {
  // The API normalizes the legacy acceptance field into acceptance_criteria.
  // Present this single concept once instead of requiring duplicate student input.
  return Object.entries(schema?.properties || {}).filter(([key]) =>
    key !== 'acceptance_criteria' || !schema.properties.acceptance)
}
