/* DOMINIUM — export PNG do resumo de códigos históricos por cidade.
   Roda somente no navegador; sem bibliotecas externas, upload ou baixa de O.S. */
(function (global, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else global.DominiumBacklogReportImage = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const palette = {
    background: "#060508",
    surface: "#110c10",
    surfaceAlt: "#170e14",
    line: "#54212e",
    accent: "#ff1744",
    white: "#f7f4f6",
    muted: "#c8bfc5",
    total: "#27040f"
  };

  function drawText(ctx, text, x, y, options = {}) {
    ctx.font = (options.bold ? "700 " : "500 ") + (options.size || 25) + "px Arial, sans-serif";
    ctx.fillStyle = options.color || palette.white;
    ctx.textAlign = options.align || "left";
    ctx.textBaseline = "middle";
    ctx.fillText(String(text), x, y);
  }

  function imageDimensions(groups) {
    const cols = Math.min(3, Math.max(1, groups.length));
    const width = cols === 3 ? 1600 : cols === 2 ? 1180 : 790;
    const margin = 72;
    const gap = 28;
    const cardWidth = (width - margin * 2 - gap * (cols - 1)) / cols;
    const rows = [];
    for (let index = 0; index < groups.length; index += cols) {
      const slice = groups.slice(index, index + cols);
      const maxCodeRows = Math.max(1, ...slice.map(g => Object.keys(g.codeCounts || {}).length));
      rows.push({ groups: slice, height: 62 + 53 + maxCodeRows * 52 + 57 });
    }
    const height = 196 + rows.reduce((sum, row) => sum + row.height, 0) +
      Math.max(0, rows.length - 1) * 34 + 120;
    return { width, height, margin, gap, cols, cardWidth, rows };
  }

  function createCanvas(report, doc) {
    if (!report || !Array.isArray(report.groups) || !report.groups.length) {
      throw new Error("Não há códigos no filtro atual para gerar a imagem");
    }
    const page = doc || document;
    const canvas = page.createElement("canvas");
    const layout = imageDimensions(report.groups);
    canvas.width = layout.width;
    canvas.height = layout.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("O navegador não disponibilizou Canvas 2D");

    ctx.fillStyle = palette.background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    drawText(ctx, "Resumo de códigos por cidade", layout.margin, 76, {
      bold: true, size: 45
    });
    drawText(ctx, "DMV · IMPERIUM · CLARO", layout.margin, 122, {
      bold: true, color: palette.accent, size: 23
    });
    drawText(ctx, "CLARO", canvas.width - layout.margin, 88, {
      bold: true, color: "#65172c", size: 49, align: "right"
    });

    let y = 196;
    for (const row of layout.rows) {
      const contentWidth = row.groups.length * layout.cardWidth +
        (row.groups.length - 1) * layout.gap;
      const offset = (canvas.width - contentWidth) / 2;
      for (const [index, city] of row.groups.entries()) {
        const x = offset + index * (layout.cardWidth + layout.gap);
        const w = layout.cardWidth;
        const half = x + w / 2;
        const headerHeight = 62;
        const codes = Object.entries(city.codeCounts || {}).sort(
          (a, b) => Number(b[1]) - Number(a[1]) || String(a[0]).localeCompare(String(b[0]))
        );
        const totalHeight = row.height;

        ctx.fillStyle = palette.surface;
        ctx.fillRect(x, y, w, totalHeight);
        const gradient = ctx.createLinearGradient(x, y, x + w, y);
        gradient.addColorStop(0, "#cb002c");
        gradient.addColorStop(1, "#fa3153");
        ctx.fillStyle = gradient;
        ctx.fillRect(x, y, w, headerHeight);
        drawText(ctx, city.label, x + w / 2, y + 32, {
          size: 25, bold: true, align: "center"
        });

        const headingY = y + headerHeight;
        drawText(ctx, "CÓDIGO", x + w * .25, headingY + 26, {
          size: 22, bold: true, align: "center"
        });
        drawText(ctx, "QUANTIDADE", x + w * .75, headingY + 26, {
          size: 22, bold: true, align: "center"
        });
        ctx.strokeStyle = palette.line;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(half, headingY);
        ctx.lineTo(half, y + totalHeight);
        ctx.stroke();

        for (let i = 0; i < codes.length; i++) {
          const rowY = headingY + 53 + i * 52;
          ctx.fillStyle = i % 2 === 0 ? palette.surface : palette.surfaceAlt;
          ctx.fillRect(x, rowY, w, 52);
          ctx.strokeStyle = palette.line;
          ctx.beginPath();
          ctx.moveTo(x, rowY);
          ctx.lineTo(x + w, rowY);
          ctx.stroke();
          drawText(ctx, codes[i][0], x + w * .25, rowY + 26, {
            size: 24, align: "center"
          });
          drawText(ctx, codes[i][1], x + w * .75, rowY + 26, {
            size: 24, align: "center"
          });
        }

        const totalY = y + totalHeight - 57;
        ctx.fillStyle = palette.total;
        ctx.fillRect(x, totalY, w, 57);
        ctx.strokeStyle = palette.line;
        ctx.strokeRect(x + .5, y + .5, w - 1, totalHeight - 1);
        ctx.beginPath();
        ctx.moveTo(half, y);
        ctx.lineTo(half, y + totalHeight);
        ctx.stroke();

        drawText(ctx, "TOTAL", x + w * .25, totalY + 28, {
          bold: true, size: 24, align: "center"
        });
        drawText(ctx, city.count, x + w * .75, totalY + 28, {
          bold: true, size: 26, align: "center"
        });
      }
      y += row.height + 34;
    }

    drawText(ctx, "DOMINIUM · Contratos da rota com histórico nos códigos selecionados", layout.margin,
      canvas.height - 76, { size: 20, color: palette.muted });
    drawText(ctx, "430 = retirada produtiva, incluída no comparativo histórico",
      layout.margin, canvas.height - 43, { size: 18, color: palette.muted });
    return canvas;
  }

  function download(report, scope, doc) {
    const page = doc || document;
    const canvas = createCanvas(report, page);
    const date = new Date().toISOString().slice(0, 10);
    const name = "DOMINIUM-codigos-" + String(scope || "todos") + "-" + date + ".png";
    return new Promise((resolve, reject) => {
      canvas.toBlob(blob => {
        if (!blob) {
          reject(new Error("Não foi possível produzir o arquivo PNG"));
          return;
        }
        const url = URL.createObjectURL(blob);
        const link = page.createElement("a");
        link.href = url;
        link.download = name;
        link.style.display = "none";
        page.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        resolve(name);
      }, "image/png");
    });
  }

  return { createCanvas, download, imageDimensions };
});
