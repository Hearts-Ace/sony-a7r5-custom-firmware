"""Read ONNX protobuf nodes/constants without loading or executing the model.

REA rejects this artifact format. Only Model.graph, Graph.node, Node attributes
and scalar FLOAT/INT64 tensor constants are decoded; this is not an ONNX runtime.
"""
import argparse, hashlib, json, struct
from pathlib import Path


def varint(b, i):
    v = shift = 0
    while True:
        x = b[i]; i += 1
        v |= (x & 127) << shift
        if x < 128:
            return v, i
        shift += 7
        if shift > 70:
            raise ValueError('Invalid protobuf varint')


def fields(b):
    i = 0
    while i < len(b):
        k, i = varint(b, i); wire = k & 7
        if wire == 0:
            v, i = varint(b, i)
        elif wire == 2:
            n, i = varint(b, i); v = b[i:i+n]; i += n
            if len(v) != n:
                raise ValueError('Truncated protobuf')
        elif wire in (1, 5):
            n = 8 if wire == 1 else 4; v = b[i:i+n]; i += n
        else:
            raise ValueError('Unsupported protobuf wire type')
        yield k >> 3, wire, v


def scalar(t):
    f = list(fields(t))
    typ = next(v for k, w, v in f if k == 2)
    raw = next((v for k, w, v in f if k == 9), None)
    if raw is not None:
        fmt = {1: '<f', 7: '<q'}.get(typ)
        if fmt and len(raw) == struct.calcsize(fmt):
            return struct.unpack(fmt, raw)[0]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('model', type=Path); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(); raw = a.model.read_bytes()
    g = next(v for k, w, v in fields(raw) if k == 7)
    nodes = []; constants = {}
    for k, w, v in fields(g):
        if k != 1:
            continue
        f = list(fields(v))
        node = dict(name=next((x.decode() for n, w, x in f if n == 3), ''),
                    op=next(x.decode() for n, w, x in f if n == 4),
                    inputs=[x.decode() for n, w, x in f if n == 1],
                    outputs=[x.decode() for n, w, x in f if n == 2])
        if node['op'] == 'Constant':
            for n, w, att in f:
                if n == 5:
                    for ak, aw, av in fields(att):
                        if ak == 5:
                            value = scalar(av)
                            if value is not None:
                                constants[node['outputs'][0]] = value
        nodes.append(node)
    by_name = {n['name']: n for n in nodes}
    checks = {}
    for name in ['/Clip_3', '/Clip_4', '/Clip_5']:
        n = by_name[name]
        checks[name] = dict(node=n, lower_bound=constants[n['inputs'][1]])
    assert checks['/Clip_3']['lower_bound'] == checks['/Clip_4']['lower_bound'] == 0
    assert by_name['/Einsum_1']['inputs'] == ['mat_b', by_name['/Clip_4']['outputs'][0]]
    assert abs(checks['/Clip_5']['lower_bound'] - 1e-6) < 1e-12
    result = dict(schema='RawAlchemy-installed-grade-ONNX-static/1', source=str(a.model.resolve()),
                  sha256=hashlib.sha256(raw).hexdigest(), nodes=nodes, scalar_constants=constants,
                  checks=checks, passed=True,
                  limitation='Static node/constant inspection only; no execution-provider placement claim.')
    with a.output.open('x') as out:
        out.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(sha256=result['sha256'], checks=checks, passed=True), indent=2))


if __name__ == '__main__':
    main()
