import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ChevronRight, ChevronDown, Plus, Trash2, FolderOpen, Folder } from 'lucide-react';
import { api } from '@/api/client';

interface Category {
  id: number;
  name: string;
  parent_id: number | null;
}

interface TreeNode extends Category {
  children: TreeNode[];
}

function buildTree(flat: Category[]): TreeNode[] {
  const map = new Map<number, TreeNode>();
  flat.forEach(c => map.set(c.id, { ...c, children: [] }));
  const roots: TreeNode[] = [];
  map.forEach(node => {
    if (node.parent_id == null) {
      roots.push(node);
    } else {
      const parent = map.get(node.parent_id);
      if (parent) parent.children.push(node);
    }
  });
  // сортируем дочерние по имени
  function sortChildren(nodes: TreeNode[]) {
    nodes.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    nodes.forEach(n => sortChildren(n.children));
  }
  sortChildren(roots);
  return roots;
}

function CategoryNode({
  node,
  depth,
  onAddChild,
  onDelete,
}: {
  node: TreeNode;
  depth: number;
  onAddChild: (parentId: number, parentName: string) => void;
  onDelete: (id: number, name: string) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-1 py-1 px-2 rounded hover:bg-gray-50 group"
        style={{ paddingLeft: `${8 + depth * 20}px` }}
      >
        <button
          onClick={() => setExpanded(e => !e)}
          className="w-4 h-4 flex items-center justify-center text-gray-400 flex-shrink-0"
        >
          {hasChildren
            ? expanded
              ? <ChevronDown size={14} />
              : <ChevronRight size={14} />
            : null}
        </button>
        <span className="text-gray-400 flex-shrink-0">
          {hasChildren
            ? expanded ? <FolderOpen size={14} /> : <Folder size={14} />
            : <Folder size={14} className="opacity-40" />}
        </span>
        <span className="text-sm text-gray-800 flex-1 select-none">{node.name}</span>
        <span className="text-xs text-gray-400 opacity-0 group-hover:opacity-100 mr-1">#{node.id}</span>
        <button
          onClick={() => onAddChild(node.id, node.name)}
          title="Добавить подкатегорию"
          className="opacity-0 group-hover:opacity-100 p-0.5 text-blue-500 hover:text-blue-700 rounded"
        >
          <Plus size={13} />
        </button>
        <button
          onClick={() => onDelete(node.id, node.name)}
          title="Удалить"
          className="opacity-0 group-hover:opacity-100 p-0.5 text-red-400 hover:text-red-600 rounded"
        >
          <Trash2 size={13} />
        </button>
      </div>
      {expanded && node.children.map(child => (
        <CategoryNode
          key={child.id}
          node={child}
          depth={depth + 1}
          onAddChild={onAddChild}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

export default function CategoryManager() {
  const qc = useQueryClient();
  const [addModal, setAddModal] = useState<{ parentId: number | null; parentName: string | null } | null>(null);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['refs/categories'],
    queryFn: () => api.get<Category[]>('/refs/categories'),
  });

  const categories = Array.isArray(data) ? data : [];
  const tree = buildTree(categories);

  function openAdd(parentId: number | null, parentName: string | null) {
    setNewName('');
    setAddModal({ parentId, parentName });
  }

  async function handleAdd() {
    if (!newName.trim() || saving) return;
    setSaving(true);
    try {
      await api.post('/refs/categories', { name: newName.trim(), parent_id: addModal?.parentId ?? null });
      qc.invalidateQueries({ queryKey: ['refs/categories'] });
      toast.success(`Категория "${newName.trim()}" создана`);
      setAddModal(null);
    } catch (e: any) {
      toast.error(e?.message ?? 'Ошибка при создании');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number, name: string) {
    if (!confirm(`Удалить категорию "${name}"?`)) return;
    try {
      await api.delete(`/refs/categories/${id}`);
      qc.invalidateQueries({ queryKey: ['refs/categories'] });
      toast.success(`Категория "${name}" удалена`);
    } catch (e: any) {
      toast.error(e?.message ?? 'Ошибка при удалении');
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">
          Категории
          <span className="ml-2 text-sm font-normal text-gray-500">{categories.length} всего</span>
        </h1>
        <button
          onClick={() => openAdd(null, null)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          <Plus size={14} /> Новая корневая
        </button>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="p-6 text-gray-400 text-sm">Загрузка...</div>
        ) : tree.length === 0 ? (
          <div className="p-6 text-gray-400 text-sm text-center">Категорий нет</div>
        ) : (
          <div className="py-1">
            {tree.map(node => (
              <CategoryNode
                key={node.id}
                node={node}
                depth={0}
                onAddChild={(parentId, parentName) => openAdd(parentId, parentName)}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      {/* Модалка добавления */}
      {addModal !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-lg shadow-xl p-5 w-80">
            <h2 className="font-semibold mb-1">
              {addModal.parentId ? 'Добавить подкатегорию' : 'Новая корневая категория'}
            </h2>
            {addModal.parentName && (
              <div className="text-xs text-gray-500 mb-3">в: {addModal.parentName}</div>
            )}
            <input
              autoFocus
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleAdd(); if (e.key === 'Escape') setAddModal(null); }}
              placeholder="Название категории"
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 mb-3"
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setAddModal(null)}
                className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
              >
                Отмена
              </button>
              <button
                onClick={handleAdd}
                disabled={!newName.trim() || saving}
                className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
              >
                Создать
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
