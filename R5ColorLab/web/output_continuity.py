"""Training-only output regularization; no photograph-side correction or LUT.

The probe geometry and weights depend only on input colors. Neither a target,
PT output, a validation split nor predicted hue is used to construct the bank.
Lab a*b* vectors avoid the undefined hue angle of near-neutral colors.
"""
import colorsys
import hashlib
import numpy as np
from perceptual import to_lab


class ProbeBank:
    def __init__(self):
        hues = np.arange(48) / 48
        saturation = np.array([0., .2, .4, .6, .8, 1.])
        delta = 1 / 512
        chunks, mixes, masses, names = [], [], [], []
        def add(name, values, dimension, step, mass, sats=saturation):
            centers = np.stack(np.meshgrid(hues, sats, values, indexing='ij'), -1).reshape(-1, 3)
            first, last = centers.copy(), centers.copy()
            first[:, dimension] -= step; last[:, dimension] += step
            if dimension == 0:
                first[:, 0] %= 1; last[:, 0] %= 1
            else:
                first[:, dimension] = np.clip(first[:, dimension], 0, 1)
                last[:, dimension] = np.clip(last[:, dimension], 0, 1)
            colors = np.array([[colorsys.hsv_to_rgb(*a) for a in row]
                for row in np.stack([first, centers, last], 1)])
            keep = np.linalg.norm(colors[:, 2] - colors[:, 0], axis=1) > 1e-8
            colors = colors[keep]
            chunks.append(colors); mixes.append(np.full((len(colors), 1), .5))
            masses.append(np.full(len(colors), mass / len(colors)))
            names.append((name, len(colors)))
        add('dark-exposure', np.arange(1, 65) / 512, 2, delta, 3)
        add('full-exposure', [.16, .25, .4, .6, .8, 1-delta], 2, delta, 1)
        levels = [.01, .025, .05, .1, .2, .4, .65, .9, 1.]
        # Local perturbations, not coarse H/S samples that would flatten the look.
        add('hue', levels, 0, 1/360, 1)
        add('saturation', levels, 1, .02, 1, sats=saturation[1:-1])
        colors = np.concatenate(chunks)
        unique, inverse = np.unique(np.round(np.r_[colors.reshape(-1,3), [[0,0,0],[1,1,1]]], 12), axis=0, return_inverse=True)
        self.rgb = unique
        self.triplets = inverse[:-2].reshape(-1, 3)
        self.mix = np.concatenate(mixes)
        self.mass = np.concatenate(masses) / 6
        self.groups = names
        # Also probe legal pre-matrix inputs directly. A sensor-space chart
        # alone can miss the very dark pre-matrix region of real photographs.
        self.domain_size=len(self.rgb)
        count=len(self.triplets)
        self.rgb=np.tile(self.rgb,(2,1))
        self.triplets=np.r_[self.triplets,self.triplets+self.domain_size]
        self.mix=np.tile(self.mix,(2,1))
        self.mass=np.tile(self.mass/2,2)
        self.groups=names+[("native-"+name,n) for name,n in names]
        # Native pre-matrix codes precede Gamma; allow its natural dark gain.
        self.gain_limit=np.r_[np.full(count,8.),np.full(count,32.)]
        self.input_lab = to_lab(self.rgb * 255)
        # Allow input-space curvature, including the corners at pure primaries.
        self.allowance = .35 + 2 * np.linalg.norm(self.curvature(self.input_lab)[:, 1:], axis=1)
        self.distance = np.linalg.norm(self.rgb[self.triplets[:, 2]] - self.rgb[self.triplets[:, 0]], axis=1)

    def curvature(self, values):
        a, b, c = np.asarray(values)[self.triplets].transpose(1, 0, 2)
        return 2 * (b - a * (1 - self.mix) - c * self.mix)

    def inputs(self, model, white_balance=None):
        from edit_raw_front import itp_flatfield
        import white_balance as wb
        rgb=self.rgb[:self.domain_size]
        linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055)**2.4)
        codes = np.rint(512 + linear * 15871).astype('<u2')
        from sensor_encoding import encode_reference
        codes = encode_reference(codes,model)
        settings = model.settings if not wb.active(white_balance) else wb.settings_for(model, white_balance)
        front = model.sscs(itp_flatfield(codes, model.raw, settings))
        front=np.r_[front,np.rint(self.rgb[self.domain_size:]*16383).astype('<u2')]
        return np.repeat(front[:, None, :], 9, axis=1)

    def rows(self, rgb, strength):
        if not strength:
            return np.empty(0)
        rgb = np.clip(rgb, 0, 1)
        ab = self.curvature(to_lab(rgb * 255))[:, 1:]
        norm = np.linalg.norm(ab, axis=1)
        excess = np.maximum(norm - self.allowance, 0)
        # Quartic tail emphasizes rare severe jumps, rather than averaging them away.
        bend = excess * np.sqrt(1 + (excess / 2)**2) / 100
        at = self.triplets
        gain = np.linalg.norm(rgb[at[:, 2]] - rgb[at[:, 0]], axis=1) / np.maximum(self.distance, 1 / 16383)
        amplification = np.maximum(gain - self.gain_limit, 0) * .01
        return (np.stack([bend, amplification], 1) * np.sqrt(self.mass[:, None] * strength / 100 * 8)).ravel()

    def cost(self, rgb, strength):
        rows = self.rows(rgb, strength)
        return float(rows @ rows) * 255**2

    def report(self, rgb, strength):
        ab = self.curvature(to_lab(np.clip(rgb, 0, 1) * 255))[:, 1:]
        norm = np.linalg.norm(ab, axis=1)
        report = dict(enabled=bool(strength), strength=strength, probes=len(self.rgb),
            policy='local-dual-domain-v1',
            perturbation=dict(exposure_half_step=1/512,hue_half_step_degrees=1,saturation_half_step=.02),
            triplets=len(self.triplets), input_sha256=hashlib.sha256(self.rgb.tobytes()).hexdigest(),
            input_domains=['sensor + ITP + SSCS','direct post-SSCS/pre-matrix'],
            objective_cost_8bit_squared=self.cost(rgb, strength), axes={})
        at=self.triplets
        gain=np.linalg.norm(np.asarray(rgb)[at[:,2]]-np.asarray(rgb)[at[:,0]],axis=1)/np.maximum(self.distance,1/16383)
        report['rgb_gain_p95']=float(np.percentile(gain,95))
        report['rgb_gain_max']=float(gain.max())
        offset = 0
        for name, count in self.groups:
            section = norm[offset:offset + count]; offset += count
            report['axes'][name] = dict(chroma_second_difference_p95=float(np.percentile(section, 95)),
                chroma_second_difference_max=float(section.max()),
                over_allowance=int(np.count_nonzero(section>self.allowance[offset-count:offset])))
        return report


class TensorPenalty:
    def __init__(self, bank, tools, strength):
        self.tools, self.strength = tools, strength
        self.at = tools.tensor(bank.triplets, True)
        self.mix = tools.tensor(bank.mix)
        self.allowance = tools.tensor(bank.allowance)
        self.distance = tools.tensor(np.maximum(bank.distance, 1 / 16383))
        self.mass = tools.tensor(bank.mass)
        self.gain_limit=tools.tensor(bank.gain_limit)

    def loss(self, rgb):
        t = self.tools.torch
        rgb = rgb.clamp(0, 1)
        lab = self.tools.lab(rgb)
        a, b, c = lab[self.at].unbind(1)
        ab = 2 * (b - a * (1 - self.mix) - c * self.mix)[:, 1:]
        norm = t.linalg.vector_norm(ab, dim=1)
        excess = (norm - self.allowance).clamp(min=0)
        bend = excess * t.sqrt(1 + (excess / 2).square()) / 100
        gain = t.linalg.vector_norm(rgb[self.at[:, 2]] - rgb[self.at[:, 0]], dim=1) / self.distance
        amplification = (gain - self.gain_limit).clamp(min=0) * .01
        return ((bend.square() + amplification.square()) * self.mass).sum() * self.strength / 100 * 8
