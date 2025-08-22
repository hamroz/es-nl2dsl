import React, { useState, useCallback } from 'react';
import { Plus, Minus, ChevronDown, ChevronRight, Code, Play, Save } from 'lucide-react';

interface QueryCondition {
  id: string;
  field: string;
  operator: string;
  value: string | number;
  type: 'term' | 'range' | 'match' | 'wildcard' | 'exists';
}

interface QueryGroup {
  id: string;
  type: 'must' | 'should' | 'must_not' | 'filter';
  conditions: QueryCondition[];
  subGroups: QueryGroup[];
  expanded: boolean;
}

interface QueryBuilderProps {
  onQueryChange?: (query: any) => void;
  onExecute?: (query: any) => void;
  onSave?: (query: any, name: string) => void;
  availableFields?: string[];
  readonly?: boolean;
}

const FIELD_TYPES = {
  '@timestamp': 'date',
  'src_ip': 'ip',
  'dst_ip': 'ip',
  'src_port': 'number',
  'dst_port': 'number',
  'protocol': 'keyword',
  'bytes_in': 'number',
  'bytes_out': 'number',
  'label': 'keyword',
  'message': 'text',
  'attack_type': 'keyword',
  'flow_duration': 'number',
  'total_packets': 'number',
};

const OPERATORS = {
  keyword: ['equals', 'not_equals', 'exists', 'not_exists'],
  text: ['matches', 'not_matches', 'exists', 'not_exists'],
  number: ['equals', 'not_equals', 'greater_than', 'less_than', 'range', 'exists', 'not_exists'],
  date: ['equals', 'not_equals', 'greater_than', 'less_than', 'range', 'exists', 'not_exists'],
  ip: ['equals', 'not_equals', 'matches', 'exists', 'not_exists'],
};

const DEFAULT_FIELDS = [
  '@timestamp', 'src_ip', 'dst_ip', 'src_port', 'dst_port', 
  'protocol', 'bytes_in', 'bytes_out', 'label', 'message'
];

const QueryBuilder: React.FC<QueryBuilderProps> = ({
  onQueryChange,
  onExecute,
  onSave,
  availableFields = DEFAULT_FIELDS,
  readonly = false
}) => {
  const [rootGroup, setRootGroup] = useState<QueryGroup>({
    id: 'root',
    type: 'must',
    conditions: [],
    subGroups: [],
    expanded: true
  });
  
  const [showJSON, setShowJSON] = useState(false);
  const [queryName, setQueryName] = useState('');
  const [showSaveModal, setShowSaveModal] = useState(false);

  const generateId = () => Math.random().toString(36).substr(2, 9);

  const addCondition = useCallback((groupId: string) => {
    const newCondition: QueryCondition = {
      id: generateId(),
      field: availableFields[0] || '@timestamp',
      operator: 'equals',
      value: '',
      type: 'term'
    };

    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        return {
          ...group,
          conditions: [...group.conditions, newCondition]
        };
      }
      return {
        ...group,
        subGroups: group.subGroups.map(updateGroup)
      };
    };

    const updatedGroup = updateGroup(rootGroup);
    setRootGroup(updatedGroup);
    buildAndEmitQuery(updatedGroup);
  }, [rootGroup, availableFields]);

  const removeCondition = useCallback((groupId: string, conditionId: string) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        return {
          ...group,
          conditions: group.conditions.filter(c => c.id !== conditionId)
        };
      }
      return {
        ...group,
        subGroups: group.subGroups.map(updateGroup)
      };
    };

    const updatedGroup = updateGroup(rootGroup);
    setRootGroup(updatedGroup);
    buildAndEmitQuery(updatedGroup);
  }, [rootGroup]);

  const updateCondition = useCallback((groupId: string, conditionId: string, updates: Partial<QueryCondition>) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        return {
          ...group,
          conditions: group.conditions.map(c => 
            c.id === conditionId ? { ...c, ...updates } : c
          )
        };
      }
      return {
        ...group,
        subGroups: group.subGroups.map(updateGroup)
      };
    };

    const updatedGroup = updateGroup(rootGroup);
    setRootGroup(updatedGroup);
    buildAndEmitQuery(updatedGroup);
  }, [rootGroup]);

  const addSubGroup = useCallback((parentGroupId: string) => {
    const newGroup: QueryGroup = {
      id: generateId(),
      type: 'must',
      conditions: [],
      subGroups: [],
      expanded: true
    };

    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === parentGroupId) {
        return {
          ...group,
          subGroups: [...group.subGroups, newGroup]
        };
      }
      return {
        ...group,
        subGroups: group.subGroups.map(updateGroup)
      };
    };

    const updatedGroup = updateGroup(rootGroup);
    setRootGroup(updatedGroup);
    buildAndEmitQuery(updatedGroup);
  }, [rootGroup]);

  const removeSubGroup = useCallback((parentGroupId: string, groupId: string) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === parentGroupId) {
        return {
          ...group,
          subGroups: group.subGroups.filter(g => g.id !== groupId)
        };
      }
      return {
        ...group,
        subGroups: group.subGroups.map(updateGroup)
      };
    };

    const updatedGroup = updateGroup(rootGroup);
    setRootGroup(updatedGroup);
    buildAndEmitQuery(updatedGroup);
  }, [rootGroup]);

  const toggleGroup = useCallback((groupId: string) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        return { ...group, expanded: !group.expanded };
      }
      return {
        ...group,
        subGroups: group.subGroups.map(updateGroup)
      };
    };

    setRootGroup(updateGroup(rootGroup));
  }, [rootGroup]);

  const updateGroupType = useCallback((groupId: string, type: QueryGroup['type']) => {
    const updateGroup = (group: QueryGroup): QueryGroup => {
      if (group.id === groupId) {
        return { ...group, type };
      }
      return {
        ...group,
        subGroups: group.subGroups.map(updateGroup)
      };
    };

    const updatedGroup = updateGroup(rootGroup);
    setRootGroup(updatedGroup);
    buildAndEmitQuery(updatedGroup);
  }, [rootGroup]);

  const buildConditionQuery = (condition: QueryCondition) => {
    const { field, operator, value, type } = condition;

    switch (operator) {
      case 'equals':
        return { term: { [field]: value } };
      case 'not_equals':
        return { bool: { must_not: { term: { [field]: value } } } };
      case 'matches':
        return { match: { [field]: value } };
      case 'not_matches':
        return { bool: { must_not: { match: { [field]: value } } } };
      case 'greater_than':
        return { range: { [field]: { gt: value } } };
      case 'less_than':
        return { range: { [field]: { lt: value } } };
      case 'range':
        if (typeof value === 'string' && value.includes(',')) {
          const [min, max] = value.split(',');
          return { range: { [field]: { gte: min.trim(), lte: max.trim() } } };
        }
        return { range: { [field]: { gte: value, lte: value } } };
      case 'exists':
        return { exists: { field } };
      case 'not_exists':
        return { bool: { must_not: { exists: { field } } } };
      default:
        return { term: { [field]: value } };
    }
  };

  const buildGroupQuery = (group: QueryGroup): any => {
    const conditionQueries = group.conditions
      .filter(c => c.value !== '' || ['exists', 'not_exists'].includes(c.operator))
      .map(buildConditionQuery);
    
    const subGroupQueries = group.subGroups
      .map(buildGroupQuery)
      .filter(q => q !== null);

    const allQueries = [...conditionQueries, ...subGroupQueries];
    
    if (allQueries.length === 0) return null;
    if (allQueries.length === 1 && group.type === 'must') return allQueries[0];

    return {
      bool: {
        [group.type]: allQueries
      }
    };
  };

  const buildAndEmitQuery = (group: QueryGroup) => {
    const queryBody = buildGroupQuery(group);
    const elasticsearchQuery = {
      query: queryBody || { match_all: {} },
      size: 1000
    };

    onQueryChange?.(elasticsearchQuery);
  };

  const getFieldType = (field: string): string => {
    return FIELD_TYPES[field as keyof typeof FIELD_TYPES] || 'keyword';
  };

  const getAvailableOperators = (field: string): string[] => {
    const fieldType = getFieldType(field);
    return OPERATORS[fieldType as keyof typeof OPERATORS] || OPERATORS.keyword;
  };

  const renderCondition = (condition: QueryCondition, groupId: string) => {
    const fieldType = getFieldType(condition.field);
    const availableOperators = getAvailableOperators(condition.field);

    return (
      <div key={condition.id} className="flex items-center gap-2 p-2 bg-gray-50 rounded border">
        <select
          value={condition.field}
          onChange={(e) => updateCondition(groupId, condition.id, { field: e.target.value })}
          className="px-2 py-1 border rounded text-sm"
          disabled={readonly}
        >
          {availableFields.map(field => (
            <option key={field} value={field}>{field}</option>
          ))}
        </select>

        <select
          value={condition.operator}
          onChange={(e) => updateCondition(groupId, condition.id, { operator: e.target.value })}
          className="px-2 py-1 border rounded text-sm"
          disabled={readonly}
        >
          {availableOperators.map(op => (
            <option key={op} value={op}>
              {op.replace('_', ' ')}
            </option>
          ))}
        </select>

        {!['exists', 'not_exists'].includes(condition.operator) && (
          <input
            type={fieldType === 'number' ? 'number' : fieldType === 'date' ? 'datetime-local' : 'text'}
            value={condition.value}
            onChange={(e) => updateCondition(groupId, condition.id, { value: e.target.value })}
            placeholder={
              condition.operator === 'range' ? 'min,max' : 
              fieldType === 'ip' ? '192.168.1.1' :
              fieldType === 'date' ? 'YYYY-MM-DD' :
              'value'
            }
            className="px-2 py-1 border rounded text-sm flex-1"
            disabled={readonly}
          />
        )}

        {!readonly && (
          <button
            onClick={() => removeCondition(groupId, condition.id)}
            className="p-1 text-red-600 hover:text-red-800"
          >
            <Minus className="w-4 h-4" />
          </button>
        )}
      </div>
    );
  };

  const renderGroup = (group: QueryGroup, depth = 0) => {
    const indent = depth * 20;

    return (
      <div key={group.id} className={`border rounded p-3 bg-white`} style={{ marginLeft: `${indent}px` }}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => toggleGroup(group.id)}
              className="p-1 hover:bg-gray-100 rounded"
            >
              {group.expanded ? 
                <ChevronDown className="w-4 h-4" /> : 
                <ChevronRight className="w-4 h-4" />
              }
            </button>

            <select
              value={group.type}
              onChange={(e) => updateGroupType(group.id, e.target.value as QueryGroup['type'])}
              className="px-2 py-1 border rounded text-sm font-medium"
              disabled={readonly}
            >
              <option value="must">AND (must)</option>
              <option value="should">OR (should)</option>
              <option value="must_not">NOT (must_not)</option>
              <option value="filter">FILTER</option>
            </select>

            <span className="text-sm text-gray-600">
              ({group.conditions.length + group.subGroups.length} items)
            </span>
          </div>

          {!readonly && (
            <div className="flex gap-1">
              <button
                onClick={() => addCondition(group.id)}
                className="p-1 text-green-600 hover:text-green-800"
                title="Add condition"
              >
                <Plus className="w-4 h-4" />
              </button>
              <button
                onClick={() => addSubGroup(group.id)}
                className="p-1 text-blue-600 hover:text-blue-800"
                title="Add sub-group"
              >
                <Plus className="w-4 h-4" />
              </button>
              {group.id !== 'root' && (
                <button
                  onClick={() => removeSubGroup('', group.id)}
                  className="p-1 text-red-600 hover:text-red-800"
                  title="Remove group"
                >
                  <Minus className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
        </div>

        {group.expanded && (
          <div className="space-y-2">
            {group.conditions.map(condition => renderCondition(condition, group.id))}
            {group.subGroups.map(subGroup => renderGroup(subGroup, depth + 1))}
            
            {group.conditions.length === 0 && group.subGroups.length === 0 && (
              <div className="text-center py-4 text-gray-500 bg-gray-50 rounded border-dashed border-2">
                No conditions yet. Click + to add conditions or sub-groups.
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const currentQuery = buildGroupQuery(rootGroup);
  const elasticsearchQuery = {
    query: currentQuery || { match_all: {} },
    size: 1000
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Visual Query Builder</h3>
        <div className="flex gap-2">
          <button
            onClick={() => setShowJSON(!showJSON)}
            className="flex items-center gap-1 px-3 py-1 text-sm border rounded hover:bg-gray-50"
          >
            <Code className="w-4 h-4" />
            {showJSON ? 'Hide JSON' : 'Show JSON'}
          </button>
          
          {onExecute && (
            <button
              onClick={() => onExecute(elasticsearchQuery)}
              className="flex items-center gap-1 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              <Play className="w-4 h-4" />
              Execute Query
            </button>
          )}

          {onSave && (
            <button
              onClick={() => setShowSaveModal(true)}
              className="flex items-center gap-1 px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
            >
              <Save className="w-4 h-4" />
              Save Query
            </button>
          )}
        </div>
      </div>

      <div className="bg-gray-50 p-4 rounded">
        {renderGroup(rootGroup)}
      </div>

      {showJSON && (
        <div className="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm overflow-auto max-h-96">
          <pre>{JSON.stringify(elasticsearchQuery, null, 2)}</pre>
        </div>
      )}

      {/* Save Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Save Query</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Query Name
                </label>
                <input
                  type="text"
                  value={queryName}
                  onChange={(e) => setQueryName(e.target.value)}
                  placeholder="e.g., Network Anomaly Detection"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-4 mt-6">
              <button
                onClick={() => {
                  setShowSaveModal(false);
                  setQueryName('');
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onSave?.(elasticsearchQuery, queryName);
                  setShowSaveModal(false);
                  setQueryName('');
                }}
                disabled={!queryName}
                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                Save Query
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QueryBuilder;