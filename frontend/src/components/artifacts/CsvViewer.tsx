import React from 'react';

export function CsvViewer({ artifact }: { artifact: any }) {
  const lines = artifact.content.split('\n');
  const headers = lines[0]?.split(',') || [];
  const rows = lines.slice(1).filter((line: string) => line.trim());

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-white/10">
            {headers.map((header: string, i: number) => (
              <th key={i} className="text-left px-3 py-2 text-white/60 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row: string, i: number) => (
            <tr key={i} className="border-b border-white/5 hover:bg-white/5">
              {row.split(',').map((cell: string, j: number) => (
                <td key={j} className="px-3 py-2 text-white/80 font-mono">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
