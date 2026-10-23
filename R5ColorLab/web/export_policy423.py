"""Export only explicitly selected stock grids or source-bound compression.

The v4 firmware configuration remains strict. Export provenance is a Web
project field, stripped before invoking the unchanged firmware codec.
"""
import copy
import re
from pathlib import Path
import core

PARAMETERS = ('cc1_delta', 'block13', 'gamma_native_129', 'grid_5x9x9')


def configuration(project):
    if type(project) is not dict:
        raise ValueError('请选择 v4 自定义滤镜配置')
    value = copy.deepcopy(project)
    value.pop('export_sources', None)
    core.compiler.pack(value)  # Reject all old schemas, flags and fields.
    return value


def validate(project, runs):
    value = configuration(project)
    sources = project.get('export_sources', {})
    if type(sources) is not dict or set(sources) != {str(e['number']) for e in value['entries']}:
        raise ValueError('每项配置必须明确选择原厂 5×9×9 网格，或完成压缩训练')
    from stock_grids import catalog
    stock = {e['id']: e for e in catalog()}
    receipts = []
    for entry in value['entries']:
        source = sources[str(entry['number'])]
        if type(source) is not dict:
            raise ValueError('网格来源无效')
        if source.get('kind') == 'stock' and set(source) == {'kind', 'id'}:
            preset = stock.get(source['id'])
            if preset is None or entry['grid_5x9x9'] != preset['grid_5x9x9']:
                raise ValueError('原厂网格已修改或来源失效，请重新选择')
            receipts.append(dict(number=entry['number'], **source, provenance=preset['provenance']))
        elif source.get('kind') == 'compressed' and set(source) == {'kind', 'job', 'key'}:
            if not isinstance(source['job'], str) or not re.fullmatch('[0-9a-f]{32}', source['job']):
                raise ValueError('压缩任务编号无效')
            from grid_distillation import firmware_config, load_result
            job = Path(runs) / source['job']
            expected = firmware_config(job, source['key'], configuration_only=True)['entries'][0]
            if any(entry[k] != expected[k] for k in PARAMETERS):
                raise ValueError('参数与压缩结果不一致，请重新压缩或选择原厂网格')
            report, _, digest = load_result(job, source['key'])
            receipts.append(dict(number=entry['number'], **source, compression_report_sha256=digest,
                                 identity=report['identity']))
        else:
            raise ValueError('只允许原厂网格或已完成的压缩结果')
    return value, receipts
